"""Out-of-corpus detection using retrieval score and a lightweight LLM judge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import BadRequestError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.generation.prompts import OUT_OF_CORPUS_JUDGE_PROMPT
from app.retrieval.models import RetrievedChunk

RRF_REFUSAL_THRESHOLD = 0.02
JUDGE_CHUNK_CHARS = 400


@dataclass(frozen=True)
class OutOfCorpusDecision:
    score_signal_refuse: bool
    judge_signal_refuse: bool
    refuse: bool
    signals_disagree: bool
    max_rrf_score: float


class OutOfCorpusJudgeError(ValueError):
    """Raised when the out-of-corpus judge returns invalid output."""


class _JudgePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    can_answer: bool = Field(
        description="True only when the provided chunks contain enough information to answer."
    )


class OutOfCorpusDetector:
    """Decide whether a question is outside the indexed HR policy corpus."""

    def __init__(self, client: Any, deployment_name: str) -> None:
        if not deployment_name:
            raise ValueError("deployment_name is required")
        self.client = client
        self.deployment_name = deployment_name

    def decide(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        *,
        present_top_k: int = 4,
    ) -> OutOfCorpusDecision:
        max_rrf_score = max((chunk.rrf_score for chunk in retrieved), default=0.0)
        score_signal_refuse = max_rrf_score < RRF_REFUSAL_THRESHOLD
        try:
            judge_can_answer = self._judge_can_answer(
                question, retrieved[:present_top_k]
            )
        except BadRequestError as exc:
            if not _is_content_filter_error(exc):
                raise
            return OutOfCorpusDecision(
                score_signal_refuse=True,
                judge_signal_refuse=True,
                refuse=True,
                signals_disagree=False,
                max_rrf_score=max_rrf_score,
            )
        judge_signal_refuse = not judge_can_answer
        return OutOfCorpusDecision(
            score_signal_refuse=score_signal_refuse,
            judge_signal_refuse=judge_signal_refuse,
            refuse=score_signal_refuse and judge_signal_refuse,
            signals_disagree=score_signal_refuse != judge_signal_refuse,
            max_rrf_score=max_rrf_score,
        )

    def _judge_can_answer(self, question: str, chunks: list[RetrievedChunk]) -> bool:
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[
                {
                    "role": "system",
                    "content": OUT_OF_CORPUS_JUDGE_PROMPT,
                },
                {
                    "role": "user",
                    "content": _build_judge_message(question, chunks),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=200,
        )
        content = getattr(response.choices[0].message, "content", None)
        if not content:
            raise OutOfCorpusJudgeError(
                "Out-of-corpus judge returned an empty response"
            )
        try:
            payload = _JudgePayload.model_validate_json(content)
        except ValidationError as exc:
            raise OutOfCorpusJudgeError(
                "Out-of-corpus judge returned malformed JSON"
            ) from exc
        return payload.can_answer


def _build_judge_message(question: str, chunks: list[RetrievedChunk]) -> str:
    lines = [
        "Question:",
        question,
        "",
        "Retrieved chunks:",
    ]
    if not chunks:
        lines.append("(none)")
        return "\n".join(lines)

    for chunk in chunks:
        text = " ".join(chunk.text.split())[:JUDGE_CHUNK_CHARS]
        lines.extend(
            [
                f"- source: {chunk.source}",
                f"  chunk: {chunk.file_path}#{chunk.chunk_idx}",
                f"  text: {text}",
            ]
        )
    return "\n".join(lines)


def _is_content_filter_error(exc: BadRequestError) -> bool:
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return False
    error = body.get("error", body)
    if not isinstance(error, dict):
        return False
    if error.get("code") == "content_filter":
        return True
    inner = error.get("innererror")
    if isinstance(inner, dict) and inner.get("code") == "ResponsibleAIPolicyViolation":
        return True
    return False
