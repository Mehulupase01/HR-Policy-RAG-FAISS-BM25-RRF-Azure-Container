from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from openai import APIError, RateLimitError

from app.ingest.embedder import EMBEDDING_DIMENSIONS, Embedder
from app.ingest.models import Chunk


class FakeEmbeddingsEndpoint:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.exceptions: list[Exception] = []

    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        self.calls.append({"model": model, "input": input})
        if self.exceptions:
            raise self.exceptions.pop(0)

        data = [
            SimpleNamespace(embedding=[float(idx + 1)] * EMBEDDING_DIMENSIONS)
            for idx, _ in enumerate(input)
        ]
        return SimpleNamespace(data=data)


class FakeClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsEndpoint()


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def rate_limit_error() -> RateLimitError:
    err = RateLimitError.__new__(RateLimitError)
    Exception.__init__(err, "rate limited")
    return err


def api_error(status_code: int) -> APIError:
    err = APIError.__new__(APIError)
    Exception.__init__(err, f"api error {status_code}")
    err.status_code = status_code
    return err


def make_chunk(text: str, chunk_id: str = "chunk") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source="opengov",
        file_path=Path("policy.md"),
        chunk_idx=0,
        breadcrumb="Policy",
        text=text,
        token_count=1,
        page_marker=None,
    )


def test_embed_texts_success_returns_float32_array_with_expected_shape() -> None:
    client = FakeClient()
    embedder = Embedder(client, "text-embedding-3-large", batch_size=2)

    embeddings = embedder.embed_texts(["alpha", "beta", "gamma"])

    assert embeddings.shape == (3, EMBEDDING_DIMENSIONS)
    assert embeddings.dtype == np.float32
    assert [call["model"] for call in client.embeddings.calls] == [
        "text-embedding-3-large",
        "text-embedding-3-large",
    ]


def test_rate_limiter_sleeps_before_request_that_would_exceed_max_tpm() -> None:
    client = FakeClient()
    clock = FakeClock()
    embedder = Embedder(
        client,
        "text-embedding-3-large",
        max_tpm=3,
        batch_size=1,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    embedder.embed_texts(["alpha beta", "gamma delta"])

    assert clock.sleeps == [60.0]
    assert len(client.embeddings.calls) == 2


def test_retries_on_rate_limit_error_with_exponential_backoff() -> None:
    client = FakeClient()
    client.embeddings.exceptions.append(rate_limit_error())
    clock = FakeClock()
    embedder = Embedder(
        client,
        "text-embedding-3-large",
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    embeddings = embedder.embed_texts(["alpha"])

    assert embeddings.shape == (1, EMBEDDING_DIMENSIONS)
    assert clock.sleeps == [1.0]
    assert len(client.embeddings.calls) == 2


def test_retries_on_5xx_api_error() -> None:
    client = FakeClient()
    client.embeddings.exceptions.append(api_error(500))
    clock = FakeClock()
    embedder = Embedder(
        client,
        "text-embedding-3-large",
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    embeddings = embedder.embed_texts(["alpha"])

    assert embeddings.shape == (1, EMBEDDING_DIMENSIONS)
    assert clock.sleeps == [1.0]
    assert len(client.embeddings.calls) == 2


def test_does_not_retry_4xx_api_error() -> None:
    client = FakeClient()
    client.embeddings.exceptions.append(api_error(400))
    clock = FakeClock()
    embedder = Embedder(
        client,
        "text-embedding-3-large",
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    with pytest.raises(APIError):
        embedder.embed_texts(["alpha"])

    assert clock.sleeps == []
    assert len(client.embeddings.calls) == 1


def test_over_limit_text_is_logged_and_skipped(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient()
    embedder = Embedder(client, "text-embedding-3-large")
    over_limit_text = "token " * 9000

    embeddings = embedder.embed_texts(["valid", over_limit_text])

    assert embeddings.shape == (1, EMBEDDING_DIMENSIONS)
    assert len(client.embeddings.calls) == 1
    assert client.embeddings.calls[0]["input"] == ["valid"]
    assert "Skipping embedding input" in caplog.text


def test_embed_chunks_returns_new_chunks_with_embeddings_and_skips_over_limit() -> None:
    client = FakeClient()
    embedder = Embedder(client, "text-embedding-3-large")
    valid_chunk = make_chunk("valid policy text", chunk_id="valid")
    over_limit_chunk = make_chunk("token " * 9000, chunk_id="over-limit")

    embedded_chunks = embedder.embed_chunks([valid_chunk, over_limit_chunk])

    assert len(embedded_chunks) == 1
    assert embedded_chunks[0].chunk_id == "valid"
    assert embedded_chunks[0] is not valid_chunk
    assert embedded_chunks[0].embedding is not None
    assert embedded_chunks[0].embedding.shape == (EMBEDDING_DIMENSIONS,)
    assert embedded_chunks[0].embedding.dtype == np.float32
