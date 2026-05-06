from __future__ import annotations

import numpy as np

from app.guardrails.disagreement import DisagreementDetector
from app.retrieval.models import RetrievedChunk


class FakeEmbeddingLookup:
    def __init__(self, embeddings: dict[str, list[float]]) -> None:
        self.embeddings = embeddings

    def get_embedding(self, chunk_id: str) -> np.ndarray:
        return np.array(self.embeddings[chunk_id], dtype=np.float32)


def chunk(chunk_id: str, source: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        source=source,  # type: ignore[arg-type]
        file_path=f"{source}.md",
        chunk_idx=0,
        breadcrumb=None,
        text=f"{source} text",
        dense_score=0.5,
        bm25_rank=1,
        rrf_score=0.03,
    )


def test_disagreement_positive_for_similar_source_centroids() -> None:
    detector = DisagreementDetector(
        FakeEmbeddingLookup(
            {
                "opengov-1": [1.0, 0.0, 0.0],
                "madetech-1": [0.95, 0.05, 0.0],
            }
        )
    )

    info = detector.detect(
        [
            chunk("opengov-1", "opengov"),
            chunk("madetech-1", "madetech"),
        ]
    )

    assert info.multi_source is True
    assert info.topic_overlap_score is not None
    assert info.topic_overlap_score > 0.7
    assert info.surface_disagreement is True


def test_disagreement_negative_for_orthogonal_source_centroids() -> None:
    detector = DisagreementDetector(
        FakeEmbeddingLookup(
            {
                "opengov-1": [1.0, 0.0, 0.0],
                "madetech-1": [0.0, 1.0, 0.0],
            }
        )
    )

    info = detector.detect(
        [
            chunk("opengov-1", "opengov"),
            chunk("madetech-1", "madetech"),
        ]
    )

    assert info.multi_source is True
    assert info.topic_overlap_score == 0.0
    assert info.surface_disagreement is False


def test_disagreement_single_source_does_not_branch() -> None:
    detector = DisagreementDetector(
        FakeEmbeddingLookup(
            {
                "opengov-1": [1.0, 0.0, 0.0],
                "opengov-2": [0.9, 0.1, 0.0],
            }
        )
    )

    info = detector.detect(
        [
            chunk("opengov-1", "opengov"),
            chunk("opengov-2", "opengov"),
        ]
    )

    assert info.multi_source is False
    assert info.topic_overlap_score is None
    assert info.surface_disagreement is False
