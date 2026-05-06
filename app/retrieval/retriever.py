"""Hybrid dense + lexical retrieval with Reciprocal Rank Fusion."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from time import perf_counter
from typing import Any

import faiss
import numpy as np
import pandas as pd

from app.ingest.embedder import EMBEDDING_DIMENSIONS
from app.ingest.indexer import (
    BM25_INDEX,
    EMBEDDINGS_PARQUET,
    FAISS_INDEX,
    tokenize_for_bm25,
)
from app.ingest.models import Source
from app.observability.privacy import hash_text
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Retrieve chunks from FAISS and BM25, then fuse rankings with RRF."""

    def __init__(
        self,
        faiss_index: faiss.Index,
        bm25_index: Any,
        chunks_dataframe: pd.DataFrame,
        embedder: Any,
        *,
        rrf_constant: int = 60,
        dense_pool: int = 20,
        bm25_pool: int = 20,
    ) -> None:
        if rrf_constant <= 0:
            raise ValueError("rrf_constant must be positive")
        if dense_pool <= 0:
            raise ValueError("dense_pool must be positive")
        if bm25_pool <= 0:
            raise ValueError("bm25_pool must be positive")

        self.faiss_index = faiss_index
        self.bm25_index = bm25_index
        self.chunks_dataframe = chunks_dataframe.reset_index(drop=True)
        self.embedder = embedder
        self.rrf_constant = rrf_constant
        self.dense_pool = dense_pool
        self.bm25_pool = bm25_pool
        self._normalized_embeddings = _normalized_embeddings_from_dataframe(
            self.chunks_dataframe
        )
        self._row_by_chunk_id = {
            str(row["chunk_id"]): idx for idx, row in self.chunks_dataframe.iterrows()
        }

    @classmethod
    def from_index_dir(cls, index_dir: Path | str, embedder: Any) -> "HybridRetriever":
        started = perf_counter()
        index_path = Path(index_dir)
        dataframe = pd.read_parquet(index_path / EMBEDDINGS_PARQUET)
        faiss_index = faiss.read_index(str(index_path / FAISS_INDEX))
        with (index_path / BM25_INDEX).open("rb") as file:
            bm25_index = pickle.load(file)
        logger.info(
            "retriever_index_loaded",
            extra={
                "event": "retriever_index_loaded",
                "index_dir": str(index_path),
                "chunk_count": len(dataframe),
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return cls(faiss_index, bm25_index, dataframe, embedder)

    def retrieve(self, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        started = perf_counter()
        query_hash = hash_text(query)
        query_embedding = self.embedder.embed_texts([query]).astype(np.float32)
        if query_embedding.shape != (1, EMBEDDING_DIMENSIONS):
            raise ValueError(
                f"Expected query embedding shape (1, {EMBEDDING_DIMENSIONS}); "
                f"got {query_embedding.shape}"
            )
        faiss.normalize_L2(query_embedding)

        dense_rank_by_row, dense_score_by_row = self._dense_search(query_embedding)
        bm25_rank_by_row = self._bm25_search(query)
        logger.info(
            "retrieval_candidates_ready",
            extra={
                "event": "retrieval_candidates_ready",
                "question_hash": query_hash,
                "dense_candidate_count": len(dense_rank_by_row),
                "bm25_candidate_count": len(bm25_rank_by_row),
            },
        )

        candidate_rows = set(dense_rank_by_row) | set(bm25_rank_by_row)
        fused: list[tuple[int, float]] = []
        for row_idx in candidate_rows:
            score = 0.0
            if row_idx in dense_rank_by_row:
                score += 1.0 / (self.rrf_constant + dense_rank_by_row[row_idx])
            if row_idx in bm25_rank_by_row:
                score += 1.0 / (self.rrf_constant + bm25_rank_by_row[row_idx])
            fused.append((row_idx, score))

        fused.sort(key=lambda item: item[1], reverse=True)
        results = [
            self._to_retrieved_chunk(
                row_idx=row_idx,
                query_embedding=query_embedding,
                dense_score_by_row=dense_score_by_row,
                bm25_rank_by_row=bm25_rank_by_row,
                rrf_score=rrf_score,
            )
            for row_idx, rrf_score in fused[:top_k]
        ]
        logger.info(
            "retrieval_completed",
            extra={
                "event": "retrieval_completed",
                "question_hash": query_hash,
                "returned_chunk_count": len(results),
                "candidate_union_count": len(candidate_rows),
                "top_k": top_k,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return results

    def get_embedding(self, chunk_id: str) -> np.ndarray:
        row_idx = self._row_by_chunk_id.get(chunk_id)
        if row_idx is None:
            raise KeyError(f"Unknown chunk_id: {chunk_id}")
        return np.asarray(
            self.chunks_dataframe.iloc[row_idx]["embedding"],
            dtype=np.float32,
        )

    def _dense_search(
        self, query_embedding: np.ndarray
    ) -> tuple[dict[int, int], dict[int, float]]:
        pool = min(self.dense_pool, len(self.chunks_dataframe))
        distances, indexes = self.faiss_index.search(query_embedding, pool)
        dense_rank_by_row: dict[int, int] = {}
        dense_score_by_row: dict[int, float] = {}
        for rank, (row_idx, score) in enumerate(zip(indexes[0], distances[0]), start=1):
            if row_idx < 0:
                continue
            row = int(row_idx)
            dense_rank_by_row[row] = rank
            dense_score_by_row[row] = float(score)
        return dense_rank_by_row, dense_score_by_row

    def _bm25_search(self, query: str) -> dict[int, int]:
        scores = self.bm25_index.get_scores(tokenize_for_bm25(query))
        pool = min(self.bm25_pool, len(scores))
        if pool == 0:
            return {}

        top_indexes = np.argsort(scores)[::-1][:pool]
        return {int(row_idx): rank for rank, row_idx in enumerate(top_indexes, start=1)}

    def _to_retrieved_chunk(
        self,
        *,
        row_idx: int,
        query_embedding: np.ndarray,
        dense_score_by_row: dict[int, float],
        bm25_rank_by_row: dict[int, int],
        rrf_score: float,
    ) -> RetrievedChunk:
        row = self.chunks_dataframe.iloc[row_idx]
        dense_score = dense_score_by_row.get(row_idx)
        if dense_score is None:
            dense_score = float(
                np.dot(query_embedding[0], self._normalized_embeddings[row_idx])
            )

        return RetrievedChunk(
            chunk_id=str(row["chunk_id"]),
            source=_source(row["source"]),
            file_path=str(row["file_path"]),
            chunk_idx=int(row["chunk_idx"]),
            breadcrumb=_optional_str(row.get("breadcrumb")),
            text=str(row["text"]),
            dense_score=float(dense_score),
            bm25_rank=bm25_rank_by_row.get(row_idx),
            rrf_score=float(rrf_score),
        )


def _normalized_embeddings_from_dataframe(dataframe: pd.DataFrame) -> np.ndarray:
    embeddings = np.vstack(dataframe["embedding"].to_numpy()).astype(np.float32)
    if embeddings.shape != (len(dataframe), EMBEDDING_DIMENSIONS):
        raise ValueError(
            f"Expected embeddings shape ({len(dataframe)}, {EMBEDDING_DIMENSIONS}); "
            f"got {embeddings.shape}"
        )
    faiss.normalize_L2(embeddings)
    return embeddings


def _source(value: object) -> Source:
    if value not in {"opengov", "madetech"}:
        raise ValueError(f"Unexpected source value: {value}")
    return value  # type: ignore[return-value]


def _optional_str(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)
