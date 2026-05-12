from __future__ import annotations

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.context import (
    REQUEST_ID_HEADER,
    get_request_id,
    reset_request_id,
    set_request_id,
)
from app.observability.logging import JsonFormatter
from app.observability.middleware import RequestIdMiddleware
from app.observability.rate_limit import QueryRateLimitMiddleware
from app.observability.telemetry import configure_azure_monitor_telemetry


def test_json_formatter_includes_request_id_and_extra_fields() -> None:
    token = set_request_id("req-123")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.event = "unit_test"
        record.answer_length = 42

        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_id(token)

    assert payload["request_id"] == "req-123"
    assert payload["event"] == "unit_test"
    assert payload["answer_length"] == 42
    assert payload["message"] == "hello"


def test_request_id_middleware_returns_header_and_sets_context() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str | None]:
        return {"request_id": get_request_id()}

    response = TestClient(app).get("/ping")

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_azure_monitor_telemetry_noops_without_connection_string(monkeypatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    configure_azure_monitor_telemetry()


def test_query_rate_limit_blocks_only_query_requests() -> None:
    app = FastAPI()
    app.add_middleware(
        QueryRateLimitMiddleware,
        enabled=True,
        requests_per_window=2,
        window_seconds=60,
    )

    @app.post("/query")
    def query() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    assert client.post("/query").status_code == 200
    assert client.post("/query").status_code == 200
    limited = client.post("/query")

    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert limited.json() == {
        "title": "Too Many Requests",
        "detail": "Rate limit exceeded. Please retry later.",
        "status": 429,
    }
    assert client.get("/healthz").status_code == 200


def test_query_rate_limit_can_be_disabled() -> None:
    app = FastAPI()
    app.add_middleware(
        QueryRateLimitMiddleware,
        enabled=False,
        requests_per_window=1,
        window_seconds=60,
    )

    @app.post("/query")
    def query() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    assert client.post("/query").status_code == 200
    assert client.post("/query").status_code == 200
