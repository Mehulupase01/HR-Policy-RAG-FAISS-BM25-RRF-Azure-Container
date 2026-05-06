"""Detect when retrieved context should surface multi-handbook differences."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.ingest.models import Source
from app.retrieval.models import RetrievedChunk

TOPIC_OVERLAP_THRESHOLD = 0.7


class EmbeddingLookup(Protocol):
    def get_embedding(self, chunk_id: str) -> np.ndarray:
        ...


@dataclass(frozen=True)
class DisagreementInfo:
    multi_source: bool
    topic_overlap_score: float | None
    surface_disagreement: bool


class DisagreementDetector:
    """Use source centroid similarity to decide whether to branch the prompt."""

    def __init__(
        self,
        embedding_lookup: EmbeddingLookup,
        *,
        topic_overlap_threshold: float = TOPIC_OVERLAP_THRESHOLD,
    ) -> None:
        self.embedding_lookup = embedding_lookup
        self.topic_overlap_threshold = topic_overlap_threshold

    def detect(self, retrieved: list[RetrievedChunk]) -> DisagreementInfo:
        chunks_by_source: dict[Source, list[RetrievedChunk]] = defaultdict(list)
        for chunk in retrieved:
            chunks_by_source[chunk.source].append(chunk)

        if len(chunks_by_source) < 2:
            return DisagreementInfo(
                multi_source=False,
                topic_overlap_score=None,
                surface_disagreement=False,
            )

        centroids = {
            source: _normalized_centroid(
                [self.embedding_lookup.get_embedding(chunk.chunk_id) for chunk in chunks]
            )
            for source, chunks in chunks_by_source.items()
        }
        opengov = centroids.get("opengov")
        madetech = centroids.get("madetech")
        if opengov is None or madetech is None:
            return DisagreementInfo(
                multi_source=True,
                topic_overlap_score=None,
                surface_disagreement=False,
            )

        topic_overlap_score = float(np.dot(opengov, madetech))
        return DisagreementInfo(
            multi_source=True,
            topic_overlap_score=topic_overlap_score,
            surface_disagreement=topic_overlap_score > self.topic_overlap_threshold,
        )


def _normalized_centroid(embeddings: list[np.ndarray]) -> np.ndarray:
    if not embeddings:
        raise ValueError("Cannot compute centroid from no embeddings")
    centroid = np.vstack(embeddings).astype(np.float32).mean(axis=0)
    norm = np.linalg.norm(centroid)
    if norm == 0:
        return centroid
    return centroid / norm
