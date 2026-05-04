"""Data models for corpus ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray


Source = Literal["opengov", "madetech"]
DocumentFormat = Literal["md", "pdf"]


@dataclass(frozen=True)
class RawDocument:
    file_path: Path
    source: Source
    format: DocumentFormat
    content: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: Source
    file_path: Path
    chunk_idx: int
    breadcrumb: str | None
    text: str
    token_count: int
    page_marker: int | None
    embedding: NDArray[np.float32] | None = None
