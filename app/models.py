"""Pydantic models for public API contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class QueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    top_k: int | None = Field(default=None, ge=1)


class Citation(BaseModel):
    file_path: str
    source: Literal["opengov", "madetech"]
    chunk_idx: int
    snippet: str


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]
    retrieval_scores: list[float] | None
