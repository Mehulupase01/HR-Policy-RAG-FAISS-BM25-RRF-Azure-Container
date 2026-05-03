"""Qdrant-backed retriever with retry logic."""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, Iterable, List

from agent.rag_agent import ChatMessage, RetrievalResult

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import ResponseHandlingException
except ImportError:
    QdrantClient = None  # type: ignore[assignment,misc]
    ResponseHandlingException = Exception  # type: ignore[assignment,misc]


class QdrantRetriever:
    """Retrieve relevant chunks from a Qdrant collection."""

    def __init__(
        self,
        client: "QdrantClient",
        collection_name: str,
        embed_fn: Callable[[str], List[float]],
        top_k: int = 5,
    ):
        self.client = client
        self.collection_name = collection_name
        self.embed_fn = embed_fn
        self.top_k = top_k
        self.retry_attempts = max(int(os.getenv("QDRANT_RETRY_ATTEMPTS", "2")), 1)
        self.retry_delay = float(os.getenv("QDRANT_RETRY_DELAY_SECONDS", "1.5"))

    def retrieve(self, question: str, chat_history: Iterable[ChatMessage]) -> List[RetrievalResult]:
        vector = self.embed_fn(question)

        results = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=vector,
                    limit=self.top_k,
                )
                break
            except ResponseHandlingException as exc:
                logger.warning("Qdrant search attempt %s/%s failed: %s", attempt, self.retry_attempts, exc)
                if attempt == self.retry_attempts:
                    logger.error("All Qdrant search attempts failed; returning no results")
                    return []
                time.sleep(min(self.retry_delay * attempt, 5.0))

        if results is None:
            return []

        parsed: List[RetrievalResult] = []
        for res in results:
            payload = getattr(res, "payload", {}) or {}
            text = payload.get("text") or payload.get("content") or ""
            score = getattr(res, "score", 0.0)
            source = payload.get("source") or payload.get("blob_name")
            parsed.append(RetrievalResult(text=text, score=score, source=source))

        return parsed
