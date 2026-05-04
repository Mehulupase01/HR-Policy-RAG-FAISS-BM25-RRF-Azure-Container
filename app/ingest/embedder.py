"""Azure OpenAI embedding client wrapper for ingestion."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

import numpy as np
import tiktoken
from numpy.typing import NDArray
from openai import APIError, APIStatusError, RateLimitError

from app.ingest.models import Chunk


EMBEDDING_DIMENSIONS = 3072
MAX_EMBEDDING_INPUT_TOKENS = 8191

_ENCODING = tiktoken.get_encoding("cl100k_base")

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Sliding-window token limiter for Azure OpenAI TPM quota."""

    def __init__(
        self,
        max_tpm: int,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_tpm <= 0:
            raise ValueError("max_tpm must be positive")
        self.max_tpm = max_tpm
        self._events: deque[tuple[float, int]] = deque()
        self._monotonic = monotonic
        self._sleep = sleep

    def acquire(self, tokens: int) -> None:
        if tokens <= 0:
            return
        if tokens > self.max_tpm:
            raise ValueError(
                f"Single request token count {tokens} exceeds max_tpm {self.max_tpm}"
            )

        while True:
            now = self._monotonic()
            self._drop_expired(now)
            spent_tokens = sum(event_tokens for _, event_tokens in self._events)
            if spent_tokens + tokens <= self.max_tpm:
                self._events.append((now, tokens))
                return

            oldest_timestamp, _ = self._events[0]
            sleep_seconds = max(0.0, 60.0 - (now - oldest_timestamp))
            self._sleep(sleep_seconds)

    def _drop_expired(self, now: float) -> None:
        while self._events and now - self._events[0][0] >= 60.0:
            self._events.popleft()


class Embedder:
    """Batching, retrying, rate-limited embedding wrapper."""

    def __init__(
        self,
        client: Any,
        deployment_name: str,
        *,
        max_tpm: int = 25_000,
        batch_size: int = 16,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        max_retries: int = 3,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.client = client
        self.deployment_name = deployment_name
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._sleep = sleep
        self._rate_limiter = TokenBucketRateLimiter(
            max_tpm=max_tpm,
            monotonic=monotonic,
            sleep=sleep,
        )

    def embed_texts(self, texts: list[str]) -> NDArray[np.float32]:
        embeddings: list[list[float]] = []

        for batch in _batched(self._valid_texts(texts), self.batch_size):
            if not batch:
                continue
            batch_tokens = sum(_token_count(text) for text in batch)
            self._rate_limiter.acquire(batch_tokens)
            embeddings.extend(self._create_embeddings(batch))

        if not embeddings:
            return np.empty((0, EMBEDDING_DIMENSIONS), dtype=np.float32)

        array = np.asarray(embeddings, dtype=np.float32)
        if array.ndim != 2 or array.shape[1] != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Expected embeddings with shape (N, {EMBEDDING_DIMENSIONS}); got {array.shape}"
            )
        return array

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[Chunk]:
        valid_chunks: list[Chunk] = []
        valid_texts: list[str] = []

        for chunk in chunks:
            if self._is_valid_input(chunk.text, identifier=chunk.chunk_id):
                valid_chunks.append(chunk)
                valid_texts.append(chunk.text)

        embeddings = self.embed_texts(valid_texts)
        if embeddings.shape[0] != len(valid_chunks):
            raise RuntimeError("Embedding count does not match valid chunk count")

        return [
            replace(chunk, embedding=embeddings[idx].copy())
            for idx, chunk in enumerate(valid_chunks)
        ]

    def _valid_texts(self, texts: Sequence[str]) -> list[str]:
        valid_texts: list[str] = []
        for idx, text in enumerate(texts):
            if self._is_valid_input(text, identifier=str(idx)):
                valid_texts.append(text)
        return valid_texts

    def _is_valid_input(self, text: str, *, identifier: str) -> bool:
        input_tokens = _token_count(text)
        if input_tokens > MAX_EMBEDDING_INPUT_TOKENS:
            logger.warning(
                "Skipping embedding input %s because it has %s tokens, exceeding limit %s",
                identifier,
                input_tokens,
                MAX_EMBEDDING_INPUT_TOKENS,
            )
            return False
        return True

    def _create_embeddings(self, batch: list[str]) -> list[list[float]]:
        for attempt in range(self.max_retries + 1):
            try:
                # Azure OpenAI Python docs confirm `model` is the Azure deployment name:
                # https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/switching-endpoints
                response = self.client.embeddings.create(
                    model=self.deployment_name,
                    input=batch,
                )
                return [item.embedding for item in response.data]
            except Exception as exc:
                if not _is_retryable(exc):
                    raise
                if attempt >= self.max_retries:
                    raise
                sleep_seconds = 2.0**attempt
                logger.warning(
                    "Embedding request failed with retryable error; retrying in %.1f seconds",
                    sleep_seconds,
                    exc_info=exc,
                )
                self._sleep(sleep_seconds)

        raise RuntimeError("unreachable retry loop exit")


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500
    if isinstance(exc, APIError):
        status_code = getattr(exc, "status_code", None)
        return isinstance(status_code, int) and status_code >= 500
    return False


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


def _batched(items: Sequence[str], size: int) -> list[list[str]]:
    return [list(items[idx : idx + size]) for idx in range(0, len(items), size)]
