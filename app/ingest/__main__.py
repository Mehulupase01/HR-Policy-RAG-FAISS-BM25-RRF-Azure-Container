"""Run the full ingestion pipeline with `python -m app.ingest`."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable, TypeVar

from dotenv import load_dotenv
from openai import AzureOpenAI

from app.ingest.blob_store import BlobIndexStore
from app.ingest.chunker import chunk_documents
from app.ingest.embedder import Embedder
from app.ingest.indexer import build_indexes
from app.ingest.loader import CorpusLoader


T = TypeVar("T")

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    load_dotenv()

    corpus_root = Path(os.getenv("CORPUS_ROOT", "corpus"))
    output_dir = Path(os.getenv("INDEX_OUTPUT_DIR", "data/index"))
    blob_prefix = os.getenv("INDEX_BLOB_PREFIX", "latest")

    raw_documents = timed(
        "Loading corpus", lambda: list(CorpusLoader(corpus_root).load_all())
    )
    chunks = timed("Chunking documents", lambda: list(chunk_documents(raw_documents)))
    logger.info(
        "Prepared %s raw documents and %s chunks", len(raw_documents), len(chunks)
    )

    embedder = Embedder(
        client=_azure_openai_client_from_env(),
        deployment_name=_required_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    )
    embedded_chunks = timed("Embedding chunks", lambda: embedder.embed_chunks(chunks))
    summary = timed(
        "Building local indexes", lambda: build_indexes(embedded_chunks, output_dir)
    )
    logger.info("Index summary: %s", summary)

    storage_account_url = os.getenv("BLOB_ACCOUNT_URL")
    if storage_account_url:
        container_name = os.getenv("BLOB_INDEX_CONTAINER", "rag-index")
        store = BlobIndexStore(storage_account_url, container_name)
        timed(
            f"Uploading index artifacts to Blob prefix '{blob_prefix}'",
            lambda: store.upload_index(output_dir, blob_prefix),
        )
    else:
        logger.info("Skipping Blob upload; BLOB_ACCOUNT_URL not set")


def timed(label: str, func: Callable[[], T]) -> T:
    start = time.perf_counter()
    logger.info("%s started", label)
    result = func()
    logger.info("%s finished in %.2fs", label, time.perf_counter() - start)
    return result


def _azure_openai_client_from_env() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=_required_env("AZURE_OPENAI_KEY"),
        azure_endpoint=_required_env("AZURE_OPENAI_ENDPOINT"),
        api_version=_required_env("AZURE_OPENAI_API_VERSION"),
    )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    main()
