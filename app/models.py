"""Pydantic models for public API contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class QueryRequest(BaseModel):
    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ] = Field(description="HR policy question to answer from the indexed corpus.")
    top_k: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Number of chunks to retrieve before answer generation. The answerer "
            "currently receives the top 4 retrieved chunks for grounding."
        ),
    )


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
