"""Query endpoint for the RAG API."""

from __future__ import annotations

import logging
from collections import Counter

from fastapi import APIRouter, HTTPException, Request, status
from openai import APIError, RateLimitError

from app.generation.answerer import AnswerParseError
from app.generation.prompts import LIMITED_INFORMATION_PREFIX, REFUSAL_ANSWER
from app.guardrails.out_of_corpus import OutOfCorpusJudgeError
from app.models import QueryRequest, QueryResponse
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, request: Request) -> QueryResponse:
    """Answer an HR policy question using hybrid retrieval and grounded generation."""
    retriever = request.app.state.retriever
    answerer = request.app.state.answerer
    out_of_corpus_detector = request.app.state.out_of_corpus_detector
    disagreement_detector = request.app.state.disagreement_detector

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
        out_of_corpus = out_of_corpus_detector.decide(payload.question, retrieved, present_top_k=4)
    except OutOfCorpusJudgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Azure OpenAI returned an invalid out-of-corpus decision.",
        ) from exc
    except (RateLimitError, APIError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI is temporarily unavailable.",
        ) from exc
    logger.info(
        "out_of_corpus_decision score_refuse=%s judge_refuse=%s refuse=%s "
        "signals_disagree=%s max_rrf_score=%.6f",
        out_of_corpus.score_signal_refuse,
        out_of_corpus.judge_signal_refuse,
        out_of_corpus.refuse,
        out_of_corpus.signals_disagree,
        out_of_corpus.max_rrf_score,
    )
    if out_of_corpus.refuse:
        return QueryResponse(
            answer=REFUSAL_ANSWER,
            citations=[],
            retrieval_scores=[chunk.rrf_score for chunk in retrieved[:4]],
        )

    disagreement = disagreement_detector.detect(retrieved)
    source_counts = Counter(chunk.source for chunk in retrieved)
    logger.info(
        "disagreement_decision multi_source=%s topic_overlap_score=%s "
        "surface_disagreement=%s source_counts=%s",
        disagreement.multi_source,
        disagreement.topic_overlap_score,
        disagreement.surface_disagreement,
        dict(source_counts),
    )

    try:
        answered = answerer.answer(
            payload.question,
            retrieved,
            present_top_k=4,
            surface_disagreement=disagreement.surface_disagreement,
        )
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
        answer=_hedge_answer(answered.answer, out_of_corpus.signals_disagree),
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


def _hedge_answer(answer: str, should_hedge: bool) -> str:
    if not should_hedge:
        return answer
    if answer == REFUSAL_ANSWER:
        return answer
    if answer.startswith(LIMITED_INFORMATION_PREFIX):
        return answer
    return f"{LIMITED_INFORMATION_PREFIX}{answer[:1].lower()}{answer[1:]}"
