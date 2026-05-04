from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from app.ingest.embedder import EMBEDDING_DIMENSIONS
from app.ingest.indexer import (
    BM25_INDEX,
    EMBEDDINGS_PARQUET,
    FAISS_INDEX,
    build_indexes,
    tokenize_for_bm25,
)
from app.ingest.models import Chunk


def make_chunk(idx: int, embedding: np.ndarray) -> Chunk:
    return Chunk(
        chunk_id=f"chunk-{idx}",
        source="opengov" if idx % 2 == 0 else "madetech",
        file_path=Path(f"policy-{idx}.md"),
        chunk_idx=idx,
        breadcrumb=f"Policy {idx}",
        text=f"Policy text for chunk {idx}.",
        token_count=6,
        page_marker=None,
        embedding=embedding.astype(np.float32),
    )


def test_build_indexes_round_trips_faiss_self_search(tmp_path: Path) -> None:
    rng = np.random.default_rng(seed=42)
    embeddings = rng.random((4, EMBEDDING_DIMENSIONS), dtype=np.float32)
    chunks = [make_chunk(idx, embeddings[idx]) for idx in range(4)]

    summary = build_indexes(chunks, tmp_path)

    assert summary["chunk_count"] == 4
    assert summary["dimension"] == EMBEDDING_DIMENSIONS
    assert (tmp_path / EMBEDDINGS_PARQUET).exists()
    assert (tmp_path / FAISS_INDEX).exists()
    assert (tmp_path / BM25_INDEX).exists()

    dataframe = pd.read_parquet(tmp_path / EMBEDDINGS_PARQUET)
    assert len(dataframe) == 4
    assert list(dataframe["chunk_id"]) == [chunk.chunk_id for chunk in chunks]
    assert dataframe["vector_row"].tolist() == [0, 1, 2, 3]

    index = faiss.read_index(str(tmp_path / FAISS_INDEX))
    query_vectors = embeddings.copy()
    faiss.normalize_L2(query_vectors)

    distances, indexes = index.search(query_vectors, 1)

    assert indexes[:, 0].tolist() == [0, 1, 2, 3]
    assert np.allclose(distances[:, 0], np.ones(4), atol=1e-5)


def test_tokenize_for_bm25_lowercases_and_strips_punctuation() -> None:
    assert tokenize_for_bm25("Sick-leave, Policy!") == ["sick", "leave", "policy"]
