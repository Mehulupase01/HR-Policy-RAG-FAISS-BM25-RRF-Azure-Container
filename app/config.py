"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "index"


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
    blob_account_url: AnyHttpUrl | None = Field(default=None, alias="BLOB_ACCOUNT_URL")
    blob_index_container: str = Field(default="rag-index", alias="BLOB_INDEX_CONTAINER")
    index_blob_prefix: str = Field(default="latest", alias="INDEX_BLOB_PREFIX")
    index_local_dir: Path = Field(default=DEFAULT_INDEX_DIR, alias="INDEX_LOCAL_DIR")

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
