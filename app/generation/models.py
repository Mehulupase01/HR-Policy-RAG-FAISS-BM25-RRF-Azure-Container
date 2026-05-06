"""Models returned by the generation layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models import Citation


class AnsweredQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]
    retrieval_scores: list[float] | None = None
