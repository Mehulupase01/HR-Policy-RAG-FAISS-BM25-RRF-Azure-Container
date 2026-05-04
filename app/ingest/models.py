"""Data models for corpus ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


Source = Literal["opengov", "madetech"]
DocumentFormat = Literal["md", "pdf"]


@dataclass(frozen=True)
class RawDocument:
    file_path: Path
    source: Source
    format: DocumentFormat
    content: str
