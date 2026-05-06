from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from dotenv import load_dotenv
from openai import AzureOpenAI

from app.ingest.embedder import EMBEDDING_DIMENSIONS, Embedder
from app.retrieval.retriever import HybridRetriever


INDEX_DIR = Path(__file__).resolve().parents[1] / "data" / "index"
load_dotenv()


class FakeEmbedder:
    def __init__(self, embedding: np.ndarray) -> None:
        self.embedding = embedding.astype(np.float32).reshape(1, -1)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return self.embedding


class FakeFaissIndex:
    def search(self, query: np.ndarray, pool: int) -> tuple[np.ndarray, np.ndarray]:
        indexes = np.array([[0, 2, 3, 4, 1]], dtype=np.int64)
        scores = np.array([[0.99, 0.90, 0.80, 0.70, 0.10]], dtype=np.float32)
        return scores[:, :pool], indexes[:, :pool]


class FakeBm25:
    def get_scores(self, tokens: list[str]) -> np.ndarray:
        scores = np.zeros(8, dtype=np.float32)
        scores[1] = 100.0
        scores[5] = 90.0
        scores[6] = 80.0
        scores[7] = 70.0
        scores[0] = 60.0
        return scores


def real_index_available() -> bool:
    return all(
        (INDEX_DIR / filename).exists()
        for filename in ("embeddings.parquet", "faiss.index", "bm25.pkl")
    )


@pytest.fixture(scope="session")
def real_retriever() -> HybridRetriever:
    if not real_index_available():
        pytest.skip("Real Phase 6 artifacts are required in data/index/")

    required_env = [
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    ]
    if any(not os.getenv(name) for name in required_env):
        pytest.skip(
            "Azure OpenAI environment variables are required for real retrieval tests"
        )

    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )
    embedder = Embedder(
        client=client,
        deployment_name=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
    )
    return HybridRetriever.from_index_dir(INDEX_DIR, embedder)


def synthetic_dataframe() -> pd.DataFrame:
    embeddings = np.zeros((8, EMBEDDING_DIMENSIONS), dtype=np.float32)
    embeddings[0, 0] = 1.0
    embeddings[1, 1] = 1.0
    for row_idx in range(2, 8):
        embeddings[row_idx, row_idx] = 1.0

    return pd.DataFrame(
        {
            "chunk_id": [f"chunk-{idx}" for idx in range(8)],
            "source": [
                "opengov",
                "madetech",
                "opengov",
                "madetech",
                "opengov",
                "madetech",
                "opengov",
                "madetech",
            ],
            "file_path": [f"policy-{idx}.md" for idx in range(8)],
            "chunk_idx": list(range(8)),
            "breadcrumb": [None] * 8,
            "text": [f"chunk text {idx}" for idx in range(8)],
            "token_count": [3] * 8,
            "page_marker": [None] * 8,
            "vector_row": list(range(8)),
            "embedding": [embedding.tolist() for embedding in embeddings],
        }
    )


def test_rrf_combines_dense_and_bm25_pools() -> None:
    query_embedding = np.zeros(EMBEDDING_DIMENSIONS, dtype=np.float32)
    query_embedding[0] = 1.0
    retriever = HybridRetriever(
        faiss_index=FakeFaissIndex(),  # type: ignore[arg-type]
        bm25_index=FakeBm25(),
        chunks_dataframe=synthetic_dataframe(),
        embedder=FakeEmbedder(query_embedding),
        dense_pool=5,
        bm25_pool=5,
    )

    results = retriever.retrieve("query", top_k=2)

    assert {result.chunk_id for result in results} == {"chunk-0", "chunk-1"}


def test_get_embedding_returns_chunk_embedding_by_id() -> None:
    query_embedding = np.zeros(EMBEDDING_DIMENSIONS, dtype=np.float32)
    query_embedding[0] = 1.0
    retriever = HybridRetriever(
        faiss_index=FakeFaissIndex(),  # type: ignore[arg-type]
        bm25_index=FakeBm25(),
        chunks_dataframe=synthetic_dataframe(),
        embedder=FakeEmbedder(query_embedding),
    )

    embedding = retriever.get_embedding("chunk-1")

    assert embedding.dtype == np.float32
    assert embedding.shape == (EMBEDDING_DIMENSIONS,)
    assert embedding[1] == 1.0


def test_verbatim_phrase_returns_known_chunk_at_rank_1(
    real_retriever: HybridRetriever,
) -> None:
    results = real_retriever.retrieve("organizational Google Suite account", top_k=8)

    assert results[0].file_path == "email-and-password-policy.md"


def test_paraphrase_time_off_when_ill_includes_sick_leave(
    real_retriever: HybridRetriever,
) -> None:
    results = real_retriever.retrieve("time off when ill", top_k=8)

    assert any(
        "sick" in result.file_path.lower() or "sick" in result.text.lower()
        for result in results
    )


def test_sick_days_query_covers_both_sources(real_retriever: HybridRetriever) -> None:
    results = real_retriever.retrieve("How many sick days?", top_k=8)
    sources = {result.source for result in results}

    if sources != {"opengov", "madetech"}:
        formatted = "\n".join(
            f"{idx + 1}. {result.source} {result.file_path} "
            f"dense={result.dense_score:.3f} bm25_rank={result.bm25_rank} "
            f"rrf={result.rrf_score:.4f} text={result.text[:160]!r}"
            for idx, result in enumerate(results)
        )
        pytest.fail(f"Expected both sources in top 8. Actual top 8:\n{formatted}")


def test_out_of_corpus_stock_price_has_low_dense_score(
    real_retriever: HybridRetriever,
) -> None:
    results = real_retriever.retrieve("What is the company stock price?", top_k=8)

    assert max(result.dense_score for result in results) < 0.45
