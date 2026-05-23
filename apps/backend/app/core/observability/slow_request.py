"""Slow-request log middleware.

Emits a `http.slow_request` log line whenever a request's wall time exceeds
`SLOW_REQUEST_THRESHOLD_MS`. Captures the route template (not the raw path),
HTTP method, status code, and elapsed milliseconds. Intentionally cheap — no
DB writes, no metrics export — purely a forensic trail so the next
intermittent hang is attributable.

Threshold rationale: 500 ms. Below that is normal variance for endpoints that
hit Postgres + audit log. Above that warrants investigation.
"""

from __future__ import annotations

import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.observability.service import get_logger

log = get_logger("observability.slow_request")

SLOW_REQUEST_THRESHOLD_MS = 500


class SlowRequestLogMiddleware:
    """ASGI middleware that times each HTTP request and logs slow ones."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        status_holder: dict[str, int] = {"status": 0}

        async def _send(message: dict) -> None:  # type: ignore[type-arg]
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        started = time.perf_counter()
        try:
            await self._app(scope, receive, _send)
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if elapsed_ms >= SLOW_REQUEST_THRESHOLD_MS:
                route = _route_template(scope)
                log.warning(
                    "http.slow_request",
                    method=scope.get("method"),
                    route=route,
                    path=scope.get("path"),
                    status=status_holder["status"],
                    duration_ms=elapsed_ms,
                )


def _route_template(scope: Scope) -> str | None:
    """Pull the matched route template (e.g. `/api/tickets/{ticket_id}`) so log
    lines aggregate across path-parameter variants. Falls back to None when the
    route hasn't been resolved (e.g., 404 before routing)."""
    route = scope.get("route")
    if route is None:
        return None
    return getattr(route, "path", None)


# Convenience consumer used by the app factory to keep the wiring obvious.
def install(app, *, threshold_ms: int | None = None) -> None:  # type: ignore[no-untyped-def]
    """Mount the middleware on a FastAPI app."""
    if threshold_ms is not None:
        # Tests / dev can dial this down; default 500ms is the prod value.
        global SLOW_REQUEST_THRESHOLD_MS
        SLOW_REQUEST_THRESHOLD_MS = threshold_ms
    app.add_middleware(SlowRequestLogMiddleware)


__all__ = [
    "SLOW_REQUEST_THRESHOLD_MS",
    "SlowRequestLogMiddleware",
    "install",
]
