"""Adapter from the hybrid retriever to the reference SDK retriever protocol."""

from __future__ import annotations

from typing import Sequence

from app.retrieval.retriever import HybridRetriever
from sdk.backend.agent.rag_agent import ChatMessage, RetrievalResult


class SDKRetrieverAdapter:
    """Expose HybridRetriever through the SDK's Retriever protocol."""

    def __init__(self, retriever: HybridRetriever, top_k: int = 8) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self.retriever = retriever
        self.top_k = top_k

    def retrieve(
        self,
        question: str,
        chat_history: Sequence[ChatMessage] | None = None,
    ) -> list[RetrievalResult]:
        _ = chat_history
        chunks = self.retriever.retrieve(question, top_k=self.top_k)
        return [
            RetrievalResult(
                text=chunk.text,
                score=chunk.dense_score,
                source=f"{chunk.file_path}#{chunk.chunk_idx}",
            )
            for chunk in chunks
        ]
