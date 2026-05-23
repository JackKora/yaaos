"""Slow-request middleware: logs only when wall time exceeds the threshold."""

from __future__ import annotations

import asyncio

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.observability import slow_request as slow_request_module
from app.core.observability.slow_request import SlowRequestLogMiddleware


def _app_with(handler, threshold_ms: int) -> FastAPI:  # type: ignore[no-untyped-def]
    slow_request_module.SLOW_REQUEST_THRESHOLD_MS = threshold_ms
    app = FastAPI()
    app.add_middleware(SlowRequestLogMiddleware)
    app.get("/probe")(handler)
    return app


@pytest.fixture
def log_capture():  # type: ignore[no-untyped-def]
    """Swap structlog's processors for an in-memory list so tests can assert
    on the event-dict shape directly."""
    cap = structlog.testing.LogCapture()
    original = structlog.get_config()
    structlog.configure(processors=[cap])
    try:
        yield cap
    finally:
        structlog.configure(**original)


def test_fast_request_does_not_log(log_capture) -> None:  # type: ignore[no-untyped-def]
    async def handler() -> dict:
        return {"ok": True}

    app = _app_with(handler, threshold_ms=500)
    with TestClient(app) as c:
        assert c.get("/probe").status_code == 200
    assert all(e.get("event") != "http.slow_request" for e in log_capture.entries)


@pytest.mark.asyncio
async def test_slow_request_logs_with_duration(log_capture) -> None:  # type: ignore[no-untyped-def]
    async def handler() -> dict:
        await asyncio.sleep(0.05)
        return {"ok": True}

    # Threshold below the handler's 50ms delay so the middleware fires.
    app = _app_with(handler, threshold_ms=10)
    with TestClient(app) as c:
        assert c.get("/probe").status_code == 200
    slow = [e for e in log_capture.entries if e.get("event") == "http.slow_request"]
    assert len(slow) == 1
    assert slow[0]["method"] == "GET"
    assert slow[0]["path"] == "/probe"
    assert slow[0]["status"] == 200
    assert slow[0]["duration_ms"] >= 10
