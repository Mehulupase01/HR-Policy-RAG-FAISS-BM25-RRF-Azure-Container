"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    Required fields intentionally have no defaults so startup fails fast when the
    deployment environment is incomplete.
    """

    azure_openai_endpoint: AnyHttpUrl = Field(alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_key: SecretStr = Field(alias="AZURE_OPENAI_KEY")
    azure_openai_api_version: str = Field(alias="AZURE_OPENAI_API_VERSION")
    azure_openai_chat_deployment: str = Field(alias="AZURE_OPENAI_CHAT_DEPLOYMENT")
    azure_openai_embedding_deployment: str = Field(alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    azure_storage_account_url: AnyHttpUrl = Field(alias="AZURE_STORAGE_ACCOUNT_URL")
    azure_blob_container_name: str = Field(alias="AZURE_BLOB_CONTAINER_NAME")
    faiss_index_blob_name: str = Field(alias="FAISS_INDEX_BLOB_NAME")
    chunk_metadata_blob_name: str = Field(alias="CHUNK_METADATA_BLOB_NAME")
    bm25_blob_name: str = Field(alias="BM25_BLOB_NAME")

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Load settings once and raise a clear startup error if required values are missing."""
    try:
        return Settings()
    except ValidationError as exc:
        missing = [
            ".".join(str(part) for part in error["loc"])
            for error in exc.errors()
            if error.get("type") == "missing"
        ]
        if missing:
            names = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variable(s): {names}") from exc
        raise RuntimeError("Invalid application configuration.") from exc
