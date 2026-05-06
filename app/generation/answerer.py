"""Turn retrieved policy chunks into grounded answers with citations."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.generation.models import AnsweredQuery
from app.generation.prompts import DISAGREEMENT_INSTRUCTION, SYSTEM_PROMPT_V1
from app.models import Citation
from app.observability.privacy import hash_text
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)


class AnswerParseError(ValueError):
    """Raised when the model returns output we cannot safely parse."""


class _LLMAnswerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citation_keys: list[str] = Field(default_factory=list)


class Answerer:
    """Generate final answers from retrieved chunks using Azure OpenAI chat."""

    def __init__(self, client: Any, deployment_name: str) -> None:
        if not deployment_name:
            raise ValueError("deployment_name is required")
        self.client = client
        self.deployment_name = deployment_name

    def answer(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        present_top_k: int = 4,
        surface_disagreement: bool = False,
    ) -> AnsweredQuery:
        if not question.strip():
            raise ValueError("question is required")
        if present_top_k <= 0:
            raise ValueError("present_top_k must be positive")

        started = perf_counter()
        question_hash = hash_text(question)
        presented = _select_presented_chunks(
            retrieved,
            present_top_k,
            surface_disagreement=surface_disagreement,
        )
        user_message = _build_user_message(question, presented)
        system_prompt = SYSTEM_PROMPT_V1
        if surface_disagreement:
            system_prompt = f"{DISAGREEMENT_INSTRUCTION}\n\n{SYSTEM_PROMPT_V1}"

        logger.info(
            "answer_generation_started",
            extra={
                "event": "answer_generation_started",
                "question_hash": question_hash,
                "retrieved_chunk_count": len(retrieved),
                "presented_chunk_count": len(presented),
                "surface_disagreement": surface_disagreement,
            },
        )
        # Microsoft docs confirm JSON mode via response_format={"type": "json_object"}
        # and require "JSON" in the messages. The REST reference lists json_object
        # as a response format compatible with GPT-4o-family chat completions.
        # Docs:
        # https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/json-mode
        # https://learn.microsoft.com/en-us/azure/foundry/openai/reference
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=800,
        )

        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise AnswerParseError("Azure OpenAI returned truncated answer JSON")

        content = getattr(choice.message, "content", None)
        if not content:
            raise AnswerParseError("Azure OpenAI returned an empty answer")

        try:
            payload = _LLMAnswerPayload.model_validate_json(content)
        except ValidationError as exc:
            raise AnswerParseError(
                "Azure OpenAI returned malformed answer JSON"
            ) from exc

        citation_by_key = {
            _citation_key(chunk): Citation(
                file_path=chunk.file_path,
                source=chunk.source,
                chunk_idx=chunk.chunk_idx,
                snippet=_snippet(chunk.text),
            )
            for chunk in retrieved
        }

        citations: list[Citation] = []
        seen: set[str] = set()
        for key in payload.citation_keys[:5]:
            if key in seen:
                continue
            seen.add(key)
            citation = citation_by_key.get(key)
            if citation is None:
                logger.warning(
                    "Dropping hallucinated citation key from answer",
                    extra={
                        "event": "answer_hallucinated_citation_dropped",
                        "question_hash": question_hash,
                        "citation_key": key,
                    },
                )
                continue
            citations.append(citation)

        logger.info(
            "answer_generation_completed",
            extra={
                "event": "answer_generation_completed",
                "question_hash": question_hash,
                "answer_length": len(payload.answer),
                "citation_count": len(citations),
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return AnsweredQuery(
            answer=payload.answer,
            citations=citations,
            retrieval_scores=[chunk.rrf_score for chunk in presented]
            if presented
            else None,
        )


def _build_user_message(question: str, chunks: list[RetrievedChunk]) -> str:
    lines = [
        "Question:",
        question,
        "",
        "Context chunks:",
    ]
    if not chunks:
        lines.append("(no context chunks retrieved)")
        return "\n".join(lines)

    for chunk in chunks:
        lines.extend(
            [
                f"- citation_key: {_citation_key(chunk)}",
                f"  file_path: {chunk.file_path}",
                f"  chunk_idx: {chunk.chunk_idx}",
                f"  source: {chunk.source}",
                f"  text: {chunk.text}",
            ]
        )
    return "\n".join(lines)


def _select_presented_chunks(
    retrieved: list[RetrievedChunk],
    present_top_k: int,
    *,
    surface_disagreement: bool,
) -> list[RetrievedChunk]:
    if not surface_disagreement:
        return retrieved[:present_top_k]

    selected: list[RetrievedChunk] = []
    selected_ids: set[str] = set()
    for chunk in retrieved[:1]:
        selected.append(chunk)
        selected_ids.add(chunk.chunk_id)

    selected_sources = {chunk.source for chunk in selected}
    all_sources = {chunk.source for chunk in retrieved}
    for source in sorted(all_sources - selected_sources):
        source_chunk = next(
            (
                chunk
                for chunk in retrieved
                if chunk.source == source and chunk.chunk_id not in selected_ids
            ),
            None,
        )
        if source_chunk is not None:
            selected.append(source_chunk)
            selected_ids.add(source_chunk.chunk_id)

    for chunk in retrieved:
        if len(selected) >= present_top_k:
            break
        if chunk.chunk_id in selected_ids:
            continue
        selected.append(chunk)
        selected_ids.add(chunk.chunk_id)

    return selected[:present_top_k]


def _citation_key(chunk: RetrievedChunk) -> str:
    return f"{chunk.file_path}#{chunk.chunk_idx}"


def _snippet(text: str, max_chars: int = 300) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 3].rstrip()}..."
