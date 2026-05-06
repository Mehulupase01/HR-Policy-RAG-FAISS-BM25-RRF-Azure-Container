"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import AzureOpenAI

from app.api.health import router as health_router
from app.api.query import router as query_router
from app.config import get_settings
from app.generation.answerer import Answerer
from app.ingest.blob_store import BlobIndexStore, INDEX_FILES
from app.ingest.embedder import Embedder
from app.retrieval.retriever import HybridRetriever

logger = logging.getLogger(__name__)
INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "index"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load retrieval and generation dependencies once at startup."""
    settings = get_settings()
    app.state.settings = settings

    if not _index_artifacts_exist(INDEX_DIR):
        if settings.azure_storage_account_url is None:
            raise RuntimeError(
                "Local index artifacts are missing and AZURE_STORAGE_ACCOUNT_URL is not configured."
            )
        logger.info(
            "Local index artifacts missing; downloading Blob prefix '%s' to %s",
            settings.index_blob_prefix,
            INDEX_DIR,
        )
        store = BlobIndexStore(
            storage_account_url=str(settings.azure_storage_account_url),
            container_name=settings.azure_blob_container_name,
        )
        store.download_index(INDEX_DIR, settings.index_blob_prefix)
    else:
        logger.info("Using local index artifacts from %s", INDEX_DIR)

    openai_client = AzureOpenAI(
        api_key=settings.azure_openai_key.get_secret_value(),
        azure_endpoint=str(settings.azure_openai_endpoint),
        api_version=settings.azure_openai_api_version,
    )
    embedder = Embedder(
        client=openai_client,
        deployment_name=settings.azure_openai_embedding_deployment,
    )
    app.state.embedder = embedder
    app.state.retriever = HybridRetriever.from_index_dir(INDEX_DIR, embedder)
    app.state.answerer = Answerer(
        client=openai_client,
        deployment_name=settings.azure_openai_chat_deployment,
    )
    app.state.index_dir = INDEX_DIR
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
