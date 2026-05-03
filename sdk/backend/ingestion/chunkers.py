"""Text chunking utilities for the ingestion pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class DocumentChunk:
    chunk_id: str
    blob_name: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


def chunk_document(
    blob_name: str,
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Iterator[DocumentChunk]:
    """Split *text* into overlapping chunks and yield ``DocumentChunk`` objects."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_text(text)
    for idx, chunk_text in enumerate(chunks):
        chunk_id = hashlib.sha256(f"{blob_name}:{idx}:{chunk_text[:64]}".encode()).hexdigest()
        yield DocumentChunk(
            chunk_id=chunk_id,
            blob_name=blob_name,
            content=chunk_text,
            metadata={"source": blob_name, "chunk_index": str(idx), "text": chunk_text},
        )
