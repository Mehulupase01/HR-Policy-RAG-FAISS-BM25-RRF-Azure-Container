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
    blob_connection_string: str
    blob_container_name: str
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection_name: str
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
        blob_connection_string=_require_env("CONNECTION_STRING", "BLOB_CONNECTION_STRING"),
        blob_container_name=_require_env("BLOB_CONTAINER_NAME"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        qdrant_collection_name=os.getenv("QDRANT_COLLECTION_NAME", "documents"),
        embeddings_model_name=os.getenv("EMBEDDINGS_MODEL_NAME", "text-embedding-3-large"),
        embeddings_endpoint=embeddings_endpoint,
        embeddings_api_key=os.getenv("EMBEDDINGS_MODEL_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"),
        embeddings_api_version=os.getenv("EMBEDDINGS_API_VERSION", "2023-05-15"),
    )


def _require_env(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    raise RuntimeError(f"Missing required environment variable(s): {', '.join(keys)}")
