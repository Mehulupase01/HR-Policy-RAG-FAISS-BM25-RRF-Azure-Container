"""FastAPI middleware for request IDs and request lifecycle logs."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.observability.context import (
    REQUEST_ID_HEADER,
    reset_request_id,
    set_request_id,
)

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a generated request ID to logs and responses."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = uuid4().hex
        token = set_request_id(request_id)
        started = time.perf_counter()
        logger.info(
            "request_start",
            extra={
                "event": "request_start",
                "http_method": request.method,
                "http_path": request.url.path,
            },
        )
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception:
            logger.exception(
                "request_exception",
                extra={
                    "event": "request_exception",
                    "http_method": request.method,
                    "http_path": request.url.path,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request_end",
                extra={
                    "event": "request_end",
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_id(token)
