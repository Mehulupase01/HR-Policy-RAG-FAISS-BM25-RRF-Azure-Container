"""Query endpoint for the RAG API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from openai import APIError, RateLimitError

from app.generation.answerer import AnswerParseError
from app.generation.prompts import REFUSAL_ANSWER
from app.models import QueryRequest, QueryResponse
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, request: Request) -> QueryResponse:
    """Answer an HR policy question using hybrid retrieval and grounded generation."""
    retriever = request.app.state.retriever
    answerer = request.app.state.answerer

    try:
        retrieved = retriever.retrieve(payload.question, top_k=payload.top_k or 8)
    except (RateLimitError, APIError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI is temporarily unavailable.",
        ) from exc

    if not retrieved:
        return QueryResponse(
            answer=REFUSAL_ANSWER,
            citations=[],
            retrieval_scores=[],
        )

    _log_retrieval_context(retrieved[:4])

    try:
        answered = answerer.answer(payload.question, retrieved, present_top_k=4)
    except AnswerParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Azure OpenAI returned an invalid answer payload.",
        ) from exc
    except (RateLimitError, APIError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI is temporarily unavailable.",
        ) from exc

    return QueryResponse(
        answer=answered.answer,
        citations=answered.citations,
        retrieval_scores=[chunk.rrf_score for chunk in retrieved[:4]],
    )


def _log_retrieval_context(chunks: list[RetrievedChunk]) -> None:
    for rank, chunk in enumerate(chunks, start=1):
        logger.info(
            "query_retrieval_context rank=%s source=%s chunk=%s#%s "
            "dense_score=%.4f bm25_rank=%s rrf_score=%.6f",
            rank,
            chunk.source,
            chunk.file_path,
            chunk.chunk_idx,
            chunk.dense_score,
            chunk.bm25_rank,
            chunk.rrf_score,
        )
