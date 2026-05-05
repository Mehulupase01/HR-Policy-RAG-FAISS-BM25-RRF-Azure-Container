"""Data models for retrieval results."""

from __future__ import annotations

from dataclasses import dataclass

from app.ingest.models import Source


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source: Source
    file_path: str
    chunk_idx: int
    breadcrumb: str | None
    text: str
    dense_score: float
    bm25_rank: int | None
    rrf_score: float
