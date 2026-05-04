"""Centralised configuration for the ingestion pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH, override=False)


@dataclass
class IngestionConfig:
    azure_storage_account_url: str
    blob_container_name: str
    faiss_index_blob_name: str
    chunk_metadata_blob_name: str
    bm25_blob_name: str
    embeddings_model_name: str
    embeddings_endpoint: str | None
    embeddings_api_key: str | None
    embeddings_api_version: str | None


def load_ingestion_config() -> IngestionConfig:
    raw_endpoint = os.getenv("EMBEDDINGS_MODEL_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
    embeddings_endpoint = raw_endpoint
    if raw_endpoint and "/openai/deployments/" in raw_endpoint:
        embeddings_endpoint = raw_endpoint.split("/openai/deployments/")[0]

    return IngestionConfig(
        azure_storage_account_url=_require_env("AZURE_STORAGE_ACCOUNT_URL"),
        blob_container_name=_require_env("AZURE_BLOB_CONTAINER_NAME"),
        faiss_index_blob_name=os.getenv("FAISS_INDEX_BLOB_NAME", "hr-policy.faiss.index"),
        chunk_metadata_blob_name=os.getenv("CHUNK_METADATA_BLOB_NAME", "hr-policy-chunks.parquet"),
        bm25_blob_name=os.getenv("BM25_BLOB_NAME", "bm25.pkl"),
        embeddings_model_name=os.getenv("EMBEDDINGS_MODEL_NAME")
        or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
        embeddings_endpoint=embeddings_endpoint,
        embeddings_api_key=os.getenv("EMBEDDINGS_MODEL_API_KEY") or os.getenv("AZURE_OPENAI_KEY"),
        embeddings_api_version=os.getenv("EMBEDDINGS_API_VERSION", "2023-05-15"),
    )


def _require_env(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    raise RuntimeError(f"Missing required environment variable(s): {', '.join(keys)}")
