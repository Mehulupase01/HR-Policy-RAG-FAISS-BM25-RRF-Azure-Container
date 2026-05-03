"""Core RAG agent — retrieve context, generate a grounded answer.

This module is intentionally LLM-provider-agnostic.  Inject a retriever and an
LLM callable to customise behaviour per project.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)

IDK_RESPONSE = "I don't have enough information in the available documents to answer that question."


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str


@dataclass
class RetrievalResult:
    text: str
    score: float
    source: Optional[str] = None


@dataclass
class AgentResult:
    reply: str
    sources: List[str] = field(default_factory=list)
    is_fallback: bool = False


# ── Retriever protocol ──────────────────────────────────────────────────────

class Retriever(Protocol):
    def retrieve(self, question: str, chat_history: List[ChatMessage]) -> List[RetrievalResult]:
        ...


class NullRetriever:
    """Returns no results — used when no vector store is configured."""

    def retrieve(self, question: str, chat_history: List[ChatMessage]) -> List[RetrievalResult]:
        return []


# ── Main entry point ────────────────────────────────────────────────────────

def generate_reply(
    question: str,
    chat_history: Optional[Sequence[ChatMessage]] = None,
    retriever: Optional[Retriever] = None,
    llm: Optional[Callable[[str, str, Sequence[ChatMessage]], str]] = None,
    similarity_threshold: float = 0.25,
    max_chunks: int = 10,
    additional_context: Optional[Iterable[str]] = None,
) -> AgentResult:
    """Generate a RAG-grounded reply.

    Parameters
    ----------
    question:
        The user's question.
    chat_history:
        Previous conversation turns.
    retriever:
        Any object satisfying the ``Retriever`` protocol.
    llm:
        Callable ``(question, context, history) -> reply_text``.
    similarity_threshold:
        Minimum score to keep a retrieval result.
    max_chunks:
        Maximum context chunks to feed to the LLM.
    additional_context:
        Extra context strings appended after retrieval results.
    """
    if not question:
        raise ValueError("question is required")

    history = list(chat_history or [])
    active_retriever = retriever or NullRetriever()

    logger.info("Retriever type: %s", type(active_retriever).__name__)
    retrieved = active_retriever.retrieve(question, history)
    logger.info("Retrieved %d results for: %s", len(retrieved), question[:80])

    # Filter by similarity threshold
    filtered = [r for r in retrieved if r.score >= similarity_threshold]
    logger.info("After threshold filter (>=%.2f): %d results", similarity_threshold, len(filtered))
    filtered = filtered[:max_chunks]

    # Fallback: if everything fell below threshold, take the best we have
    if not filtered and retrieved:
        logger.info("Using fallback: top %d from %d below-threshold results", max_chunks, len(retrieved))
        fallback = sorted(retrieved, key=lambda r: r.score, reverse=True)
        filtered = fallback[: max(1, max_chunks)]

    extra = list(additional_context or [])

    if not filtered and not extra:
        return AgentResult(reply=IDK_RESPONSE, sources=[], is_fallback=True)

    # Build combined context
    context_parts = [r.text for r in filtered] + extra
    combined_context = "\n".join(context_parts)

    if llm is None:
        # No LLM configured — return raw context
        primary = filtered[0] if filtered else None
        reply = primary.text if primary else extra[0]
        sources = list({r.source for r in filtered if r.source})
        return AgentResult(reply=reply, sources=sources, is_fallback=True)

    reply = llm(question, combined_context, history)
    sources = list(dict.fromkeys(r.source for r in filtered if r.source))
    is_fallback = reply.strip() == IDK_RESPONSE
    return AgentResult(reply=reply, sources=sources, is_fallback=is_fallback)
