from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.ingest.indexer import BM25_INDEX, EMBEDDINGS_PARQUET, FAISS_INDEX
from app.main import INDEX_DIR, create_app

load_dotenv()


def _live_query_enabled() -> bool:
    return os.getenv("RUN_LIVE_OPENAI_TESTS") == "1"


def _index_available(index_dir: Path = INDEX_DIR) -> bool:
    return all((index_dir / filename).exists() for filename in (EMBEDDINGS_PARQUET, FAISS_INDEX, BM25_INDEX))


@pytest.mark.live_openai
@pytest.mark.skipif(
    not _live_query_enabled(),
    reason="Set RUN_LIVE_OPENAI_TESTS=1 to run the live OpenAI query smoke test.",
)
@pytest.mark.skipif(
    not _index_available(),
    reason="Live query smoke test requires local data/index artifacts.",
)
def test_live_query_smoke_sick_days() -> None:
    client = TestClient(create_app())

    response = client.post("/query", json={"question": "How many sick days do I get?"})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["answer"], str)
    assert payload["answer"]
    assert isinstance(payload["citations"], list)
    assert isinstance(payload["retrieval_scores"], list)
