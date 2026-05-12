"""Small in-memory rate limiter for public demo protection."""

from __future__ import annotations

from collections import defaultdict, deque
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class QueryRateLimitMiddleware(BaseHTTPMiddleware):
    """Limit query requests per client over a rolling time window.

    This intentionally protects only expensive query traffic. Platform probes
    and readiness checks stay outside the limiter.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        requests_per_window: int,
        window_seconds: int,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if not self._should_limit(request):
            return await call_next(request)

        now = time.monotonic()
        client_key = self._client_key(request)
        hits = self._hits[client_key]
        self._drop_expired_hits(hits, now)

        if len(hits) >= self.requests_per_window:
            retry_after = self._retry_after_seconds(hits, now)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "event": "rate_limit_exceeded",
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "client_key": client_key,
                    "limit": self.requests_per_window,
                    "window_seconds": self.window_seconds,
                    "retry_after_seconds": retry_after,
                },
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "title": "Too Many Requests",
                    "detail": "Rate limit exceeded. Please retry later.",
                    "status": 429,
                },
            )

        hits.append(now)
        return await call_next(request)

    def _should_limit(self, request: Request) -> bool:
        return (
            self.enabled
            and self.requests_per_window > 0
            and self.window_seconds > 0
            and request.method == "POST"
            and request.url.path == "/query"
        )

    def _client_key(self, request: Request) -> str:
        if request.client is not None:
            return request.client.host
        return "unknown"

    def _drop_expired_hits(self, hits: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def _retry_after_seconds(self, hits: deque[float], now: float) -> int:
        if not hits:
            return self.window_seconds
        retry_after = self.window_seconds - (now - hits[0])
        return max(1, int(round(retry_after)))
