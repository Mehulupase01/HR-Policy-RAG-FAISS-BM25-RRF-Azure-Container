"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from time import perf_counter

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
from app.observability.logging import configure_json_logging
from app.observability.middleware import RequestIdMiddleware
from app.observability.rate_limit import QueryRateLimitMiddleware
from app.observability.telemetry import configure_azure_monitor_telemetry
from app.retrieval.retriever import HybridRetriever

configure_json_logging()
configure_azure_monitor_telemetry()
logger = logging.getLogger(__name__)
INDEX_DIR = DEFAULT_INDEX_DIR


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load retrieval and generation dependencies once at startup."""
    startup_started = perf_counter()
    settings = get_settings()
    app.state.settings = settings
    index_dir = settings.index_local_dir

    logger.info(
        "startup_dependency_load_started",
        extra={"event": "startup_dependency_load_started", "index_dir": str(index_dir)},
    )
    if not _index_artifacts_exist(index_dir):
        if settings.blob_account_url is None:
            raise RuntimeError(
                "Local index artifacts are missing and BLOB_ACCOUNT_URL is not configured."
            )
        download_started = perf_counter()
        logger.info(
            "index_download_started",
            extra={
                "event": "index_download_started",
                "blob_prefix": settings.index_blob_prefix,
                "blob_container": settings.blob_index_container,
                "index_dir": str(index_dir),
            },
        )
        store = BlobIndexStore(
            storage_account_url=str(settings.blob_account_url),
            container_name=settings.blob_index_container,
        )
        try:
            store.download_index(index_dir, settings.index_blob_prefix)
        except Exception:
            logger.exception(
                "index_download_failed",
                extra={"event": "index_download_failed", "index_dir": str(index_dir)},
            )
            raise

        if not _index_artifacts_exist(index_dir):
            received = _index_artifact_summary(index_dir)
            raise RuntimeError(
                f"Blob download finished but required index artifacts are missing: {received}"
            )
        logger.info(
            "index_download_finished",
            extra={
                "event": "index_download_finished",
                "duration_ms": round((perf_counter() - download_started) * 1000, 2),
                "files_received": _index_artifact_summary(index_dir),
            },
        )
    else:
        logger.info(
            "index_local_artifacts_found",
            extra={
                "event": "index_local_artifacts_found",
                "index_dir": str(index_dir),
                "files": _index_artifact_summary(index_dir),
            },
        )

    client_started = perf_counter()
    openai_client = AzureOpenAI(
        api_key=settings.azure_openai_key.get_secret_value(),
        azure_endpoint=str(settings.azure_openai_endpoint),
        api_version=settings.azure_openai_api_version,
    )
    logger.info(
        "azure_openai_client_configured",
        extra={
            "event": "azure_openai_client_configured",
            "duration_ms": round((perf_counter() - client_started) * 1000, 2),
        },
    )

    retriever_started = perf_counter()
    embedder = Embedder(
        client=openai_client,
        deployment_name=settings.azure_openai_embedding_deployment,
    )
    app.state.embedder = embedder
    retriever = HybridRetriever.from_index_dir(index_dir, embedder)
    app.state.retriever = retriever
    logger.info(
        "hybrid_retriever_loaded",
        extra={
            "event": "hybrid_retriever_loaded",
            "duration_ms": round((perf_counter() - retriever_started) * 1000, 2),
        },
    )

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
    logger.info(
        "startup_dependency_load_finished",
        extra={
            "event": "startup_dependency_load_finished",
            "duration_ms": round((perf_counter() - startup_started) * 1000, 2),
        },
    )
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="Azure HR Policy RAG API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        QueryRateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        requests_per_window=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(RequestIdMiddleware)
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
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "title": "Validation Error",
                "detail": exc.errors(),
                "status": 422,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
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
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception while processing %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "title": "Internal Server Error",
                "detail": "An unexpected error occurred.",
                "status": 500,
            },
        )


app = create_app()
