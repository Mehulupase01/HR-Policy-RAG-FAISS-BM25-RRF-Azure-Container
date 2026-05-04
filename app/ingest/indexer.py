"""Build local retrieval artifacts from embedded chunks."""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any, Sequence

import faiss
import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

from app.ingest.embedder import EMBEDDING_DIMENSIONS
from app.ingest.models import Chunk


EMBEDDINGS_PARQUET = "embeddings.parquet"
FAISS_INDEX = "faiss.index"
BM25_INDEX = "bm25.pkl"


def tokenize_for_bm25(text: str) -> list[str]:
    normalized = re.sub(r"[^\w\s]", " ", text.lower())
    return normalized.split()


def build_indexes(chunks_with_embeddings: Sequence[Chunk], output_dir: Path | str) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    chunks = list(chunks_with_embeddings)
    if not chunks:
        raise ValueError("Cannot build indexes from an empty chunk list")

    embeddings = _stack_embeddings(chunks)
    rows = [_chunk_to_row(chunk, vector_row=idx) for idx, chunk in enumerate(chunks)]
    dataframe = pd.DataFrame(rows)

    parquet_path = output_path / EMBEDDINGS_PARQUET
    faiss_path = output_path / FAISS_INDEX
    bm25_path = output_path / BM25_INDEX

    dataframe.to_parquet(parquet_path, index=False)

    normalized_embeddings = embeddings.copy()
    faiss.normalize_L2(normalized_embeddings)
    faiss_index = faiss.IndexFlatIP(EMBEDDING_DIMENSIONS)
    faiss_index.add(normalized_embeddings)
    faiss.write_index(faiss_index, str(faiss_path))

    tokenized_corpus = [tokenize_for_bm25(chunk.text) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    with bm25_path.open("wb") as file:
        pickle.dump(bm25, file)

    token_counts = [chunk.token_count for chunk in chunks]
    return {
        "chunk_count": len(chunks),
        "dimension": EMBEDDING_DIMENSIONS,
        "mean_tokens": float(np.mean(token_counts)),
        "file_paths": {
            "embeddings": str(parquet_path),
            "faiss": str(faiss_path),
            "bm25": str(bm25_path),
        },
    }


def _stack_embeddings(chunks: Sequence[Chunk]) -> np.ndarray:
    missing = [chunk.chunk_id for chunk in chunks if chunk.embedding is None]
    if missing:
        raise ValueError(f"Cannot build indexes; chunks missing embeddings: {missing[:5]}")

    embeddings = np.vstack([chunk.embedding for chunk in chunks]).astype(np.float32, copy=False)
    if embeddings.shape != (len(chunks), EMBEDDING_DIMENSIONS):
        raise ValueError(
            f"Expected embeddings shape ({len(chunks)}, {EMBEDDING_DIMENSIONS}); "
            f"got {embeddings.shape}"
        )
    return embeddings


def _chunk_to_row(chunk: Chunk, vector_row: int) -> dict[str, Any]:
    if chunk.embedding is None:
        raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")

    return {
        "chunk_id": chunk.chunk_id,
        "source": chunk.source,
        "file_path": chunk.file_path.as_posix(),
        "chunk_idx": chunk.chunk_idx,
        "breadcrumb": chunk.breadcrumb,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "page_marker": chunk.page_marker,
        "vector_row": vector_row,
        "embedding": chunk.embedding.astype(np.float32, copy=False).tolist(),
    }
