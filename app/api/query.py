"""Query endpoint for the RAG API."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """Return a stable mock response until retrieval and generation are implemented."""
    return QueryResponse(
        answer=f"Stub for later phase. Received question: {request.question}",
        citations=[],
        retrieval_scores=None,
    )
