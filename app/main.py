"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import logging
from time import perf_counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import AzureOpenAI

from app.api.health import router as health_router
from app.api.query import router as query_router
from app.config import DEFAULT_INDEX_DIR, get_settings
from app.generation.answerer import Answerer
from app.guardrails.disagreement import DisagreementDetector
from app.guardrails.out_of_corpus import OutOfCorpusDetector
from app.ingest.blob_store import BlobIndexStore, INDEX_FILES
from app.ingest.embedder import Embedder
from app.retrieval.retriever import HybridRetriever

logger = logging.getLogger(__name__)
INDEX_DIR = DEFAULT_INDEX_DIR


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load retrieval and generation dependencies once at startup."""
    startup_started = perf_counter()
    settings = get_settings()
    app.state.settings = settings
    index_dir = settings.index_local_dir

    logger.info("Starting application dependency load; index_dir=%s", index_dir)
    if not _index_artifacts_exist(index_dir):
        if settings.blob_account_url is None:
            raise RuntimeError(
                "Local index artifacts are missing and BLOB_ACCOUNT_URL is not configured."
            )
        download_started = perf_counter()
        logger.info(
            "Index download started; blob_prefix=%s container=%s destination=%s",
            settings.index_blob_prefix,
            settings.blob_index_container,
            index_dir,
        )
        store = BlobIndexStore(
            storage_account_url=str(settings.blob_account_url),
            container_name=settings.blob_index_container,
        )
        try:
            store.download_index(index_dir, settings.index_blob_prefix)
        except Exception:
            logger.exception("Index download failed; startup will fail rather than serve without an index.")
            raise

        if not _index_artifacts_exist(index_dir):
            received = _index_artifact_summary(index_dir)
            raise RuntimeError(f"Blob download finished but required index artifacts are missing: {received}")
        logger.info(
            "Index download finished in %.2fs; files_received=%s",
            perf_counter() - download_started,
            _index_artifact_summary(index_dir),
        )
    else:
        logger.info("Using local index artifacts from %s; files=%s", index_dir, _index_artifact_summary(index_dir))

    client_started = perf_counter()
    openai_client = AzureOpenAI(
        api_key=settings.azure_openai_key.get_secret_value(),
        azure_endpoint=str(settings.azure_openai_endpoint),
        api_version=settings.azure_openai_api_version,
    )
    logger.info("Azure OpenAI client configured in %.2fs", perf_counter() - client_started)

    retriever_started = perf_counter()
    embedder = Embedder(
        client=openai_client,
        deployment_name=settings.azure_openai_embedding_deployment,
    )
    app.state.embedder = embedder
    retriever = HybridRetriever.from_index_dir(index_dir, embedder)
    app.state.retriever = retriever
    logger.info("Hybrid retriever loaded in %.2fs", perf_counter() - retriever_started)

    app.state.answerer = Answerer(
        client=openai_client,
        deployment_name=settings.azure_openai_chat_deployment,
    )
    app.state.out_of_corpus_detector = OutOfCorpusDetector(
        client=openai_client,
        deployment_name=settings.azure_openai_chat_deployment,
    )
    app.state.disagreement_detector = DisagreementDetector(retriever)
    app.state.index_dir = index_dir
    logger.info("Application dependency load finished in %.2fs", perf_counter() - startup_started)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Refreshworks AI HR Policy RAG API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(query_router)
    _register_exception_handlers(app)
    return app


def _index_artifacts_exist(index_dir: Path) -> bool:
    return all((index_dir / filename).exists() for filename in INDEX_FILES)


def _index_artifact_summary(index_dir: Path) -> dict[str, int | None]:
    summary: dict[str, int | None] = {}
    for filename in INDEX_FILES:
        path = index_dir / filename
        summary[filename] = path.stat().st_size if path.exists() else None
    return summary


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "title": "Validation Error",
                "detail": exc.errors(),
                "status": 422,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "title": "HTTP Error",
                "detail": exc.detail,
                "status": exc.status_code,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "title": "Internal Server Error",
                "detail": "An unexpected error occurred.",
                "status": 500,
            },
        )


app = create_app()
