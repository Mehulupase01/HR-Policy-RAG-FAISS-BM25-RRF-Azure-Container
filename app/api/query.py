"""Query endpoint for the RAG API."""

from __future__ import annotations

import logging
from time import perf_counter
from collections import Counter

from fastapi import APIRouter, HTTPException, Request, status
from openai import APIError, RateLimitError

from app.generation.answerer import AnswerParseError
from app.generation.prompts import LIMITED_INFORMATION_PREFIX, REFUSAL_ANSWER
from app.guardrails.out_of_corpus import OutOfCorpusJudgeError
from app.models import QueryRequest, QueryResponse
from app.observability.privacy import hash_text
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, request: Request) -> QueryResponse:
    """Answer an HR policy question using hybrid retrieval and grounded generation."""
    started = perf_counter()
    question_hash = hash_text(payload.question)
    retrieved_count = 0
    answer_length: int | None = None
    citation_count: int | None = None
    out_of_corpus_log: dict[str, object] = {}
    disagreement_log: dict[str, object] = {}

    if not payload.question:
        logger.info(
            "query_completed",
            extra={
                "event": "query_completed",
                "question_hash": question_hash,
                "retrieved_chunk_count": 0,
                "answer_length": len(REFUSAL_ANSWER),
                "citation_count": 0,
                "total_duration_ms": round((perf_counter() - started) * 1000, 2),
                "refused": True,
                "empty_question": True,
            },
        )
        return QueryResponse(
            answer=REFUSAL_ANSWER,
            citations=[],
            retrieval_scores=[],
        )

    retriever = request.app.state.retriever
    answerer = request.app.state.answerer
    out_of_corpus_detector = request.app.state.out_of_corpus_detector
    disagreement_detector = request.app.state.disagreement_detector

    try:
        logger.info(
            "query_retrieval_started",
            extra={
                "event": "query_retrieval_started",
                "question_hash": question_hash,
                "top_k": payload.top_k or 8,
            },
        )
        retrieved = retriever.retrieve(payload.question, top_k=payload.top_k or 8)
    except (RateLimitError, APIError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI is temporarily unavailable.",
        ) from exc

    retrieved_count = len(retrieved)
    if not retrieved:
        logger.info(
            "query_completed",
            extra={
                "event": "query_completed",
                "question_hash": question_hash,
                "retrieved_chunk_count": 0,
                "answer_length": len(REFUSAL_ANSWER),
                "citation_count": 0,
                "total_duration_ms": round((perf_counter() - started) * 1000, 2),
                "refused": True,
                "empty_retrieval": True,
            },
        )
        return QueryResponse(
            answer=REFUSAL_ANSWER,
            citations=[],
            retrieval_scores=[],
        )

    _log_retrieval_context(retrieved[:4])

    try:
        logger.info(
            "query_out_of_corpus_check_started",
            extra={
                "event": "query_out_of_corpus_check_started",
                "question_hash": question_hash,
            },
        )
        out_of_corpus = out_of_corpus_detector.decide(
            payload.question, retrieved, present_top_k=4
        )
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
    out_of_corpus_log = {
        "oof_score_signal_refuse": out_of_corpus.score_signal_refuse,
        "oof_judge_signal_refuse": out_of_corpus.judge_signal_refuse,
        "oof_refuse": out_of_corpus.refuse,
        "oof_signals_disagree": out_of_corpus.signals_disagree,
        "oof_max_rrf_score": out_of_corpus.max_rrf_score,
    }
    logger.info(
        "out_of_corpus_decision",
        extra={
            "event": "out_of_corpus_decision",
            "question_hash": question_hash,
            **out_of_corpus_log,
        },
    )
    if out_of_corpus.refuse:
        logger.info(
            "query_completed",
            extra={
                "event": "query_completed",
                "question_hash": question_hash,
                "retrieved_chunk_count": retrieved_count,
                "answer_length": len(REFUSAL_ANSWER),
                "citation_count": 0,
                "total_duration_ms": round((perf_counter() - started) * 1000, 2),
                "refused": True,
                **out_of_corpus_log,
            },
        )
        return QueryResponse(
            answer=REFUSAL_ANSWER,
            citations=[],
            retrieval_scores=[chunk.rrf_score for chunk in retrieved[:4]],
        )

    disagreement = disagreement_detector.detect(retrieved)
    source_counts = Counter(chunk.source for chunk in retrieved)
    disagreement_log = {
        "disagreement_multi_source": disagreement.multi_source,
        "disagreement_topic_overlap_score": disagreement.topic_overlap_score,
        "disagreement_surface": disagreement.surface_disagreement,
        "retrieved_source_counts": dict(source_counts),
    }
    logger.info(
        "disagreement_decision",
        extra={
            "event": "disagreement_decision",
            "question_hash": question_hash,
            **disagreement_log,
        },
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

    answer = _hedge_answer(answered.answer, out_of_corpus.signals_disagree)
    answer_length = len(answer)
    citation_count = len(answered.citations)
    logger.info(
        "query_completed",
        extra={
            "event": "query_completed",
            "question_hash": question_hash,
            "retrieved_chunk_count": retrieved_count,
            "answer_length": answer_length,
            "citation_count": citation_count,
            "total_duration_ms": round((perf_counter() - started) * 1000, 2),
            "refused": answer == REFUSAL_ANSWER,
            **out_of_corpus_log,
            **disagreement_log,
        },
    )
    return QueryResponse(
        answer=answer,
        citations=answered.citations,
        retrieval_scores=[chunk.rrf_score for chunk in retrieved[:4]],
    )


def _log_retrieval_context(chunks: list[RetrievedChunk]) -> None:
    for rank, chunk in enumerate(chunks, start=1):
        logger.info(
            "query_retrieval_context",
            extra={
                "event": "query_retrieval_context",
                "rank": rank,
                "source": chunk.source,
                "file_path": chunk.file_path,
                "chunk_idx": chunk.chunk_idx,
                "dense_score": round(chunk.dense_score, 6),
                "bm25_rank": chunk.bm25_rank,
                "rrf_score": round(chunk.rrf_score, 6),
            },
        )


def _hedge_answer(answer: str, should_hedge: bool) -> str:
    if not should_hedge:
        return answer
    if answer == REFUSAL_ANSWER:
        return answer
    if answer.startswith(LIMITED_INFORMATION_PREFIX):
        return answer
    return f"{LIMITED_INFORMATION_PREFIX}{answer[:1].lower()}{answer[1:]}"
