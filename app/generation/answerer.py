"""Turn retrieved policy chunks into grounded answers with citations."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.generation.models import AnsweredQuery
from app.generation.prompts import SYSTEM_PROMPT_V1
from app.models import Citation
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
    ) -> AnsweredQuery:
        if not question.strip():
            raise ValueError("question is required")
        if present_top_k <= 0:
            raise ValueError("present_top_k must be positive")

        presented = retrieved[:present_top_k]
        user_message = _build_user_message(question, presented)

        # Microsoft docs confirm JSON mode via response_format={"type": "json_object"}
        # and require "JSON" in the messages. The REST reference lists json_object
        # as a response format compatible with GPT-4o-family chat completions.
        # Docs:
        # https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/json-mode
        # https://learn.microsoft.com/en-us/azure/foundry/openai/reference
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_V1},
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
            raise AnswerParseError("Azure OpenAI returned malformed answer JSON") from exc

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
                logger.warning("Dropping hallucinated citation key from answer: %s", key)
                continue
            citations.append(citation)

        return AnsweredQuery(
            answer=payload.answer,
            citations=citations,
            retrieval_scores=[chunk.rrf_score for chunk in presented] if presented else None,
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


def _citation_key(chunk: RetrievedChunk) -> str:
    return f"{chunk.file_path}#{chunk.chunk_idx}"


def _snippet(text: str, max_chars: int = 300) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return f"{collapsed[: max_chars - 3].rstrip()}..."
