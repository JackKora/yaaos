"""401 auth-failure response helper.

When the backend rejects a request because the session is dead (idle,
expired, revoked, or never existed) we want two things on the way out:

1. **Standardized JSON shape** — `{"error": "<reason>"}` where reason is
   one of `session_idle_expired` / `session_expired` / `unauthenticated`,
   so the SPA can map to a banner explaining why the user is back at
   `/login`.
2. **Clear the stale cookies** — the next request from the browser
   starts without `yaaos_session` / `yaaos_csrf` so it can't keep hitting
   the same 401 loop and cascading "Not signed in" errors across pages.

`AuthFailure` subclasses `HTTPException` so FastAPI's default handler
still produces a sane 401 if the custom handler isn't registered (test
apps that bypass `create_app`). `register_handler(app)` — called from
the app factory — adds the Set-Cookie clears.

`auth_failure_response()` is the equivalent for endpoints that return a
`Response` directly rather than raising (e.g. `/api/auth/me`, which is a
public route so it can't reach the dependency-side raise path).
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.auth.cookies import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME, clear_cookie_attrs

AuthFailureReason = Literal[
    "session_idle_expired",
    "session_expired",
    "unauthenticated",
]


class AuthFailure(HTTPException):
    """401 caused by a dead/missing session. Raise from FastAPI deps —
    the registered handler clears `yaaos_session` + `yaaos_csrf` on the
    way out so the browser's next request starts clean."""

    def __init__(self, reason: AuthFailureReason) -> None:
        super().__init__(status_code=401, detail={"error": reason})
        self.reason: str = reason


def auth_failure_response(reason: AuthFailureReason) -> JSONResponse:
    """JSONResponse equivalent for endpoints returning Response directly
    (no raise). Same body shape + Set-Cookie clears as the exception-
    handler path."""
    resp = JSONResponse(status_code=401, content={"error": reason})
    resp.set_cookie(**clear_cookie_attrs(SESSION_COOKIE_NAME))
    resp.set_cookie(**clear_cookie_attrs(CSRF_COOKIE_NAME))
    return resp


def register_handler(app: FastAPI) -> None:
    """Wire `AuthFailure` → 401 with cleared cookies. Called from
    `create_app`; tests that need the cookie behavior call it on their
    test app."""

    @app.exception_handler(AuthFailure)
    async def _handler(_: Request, exc: AuthFailure) -> JSONResponse:
        return auth_failure_response(exc.reason)  # type: ignore[arg-type]


__all__ = [
    "AuthFailure",
    "AuthFailureReason",
    "auth_failure_response",
    "register_handler",
]
