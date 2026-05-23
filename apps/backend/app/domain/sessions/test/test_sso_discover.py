"""Coverage for GET /api/auth/sso/discover (M06 Phase 8).

The endpoint is `public_route` — no session required (the Login page
calls it before any cookie is set). Returns `provider: "github"` as the
POC fallback; the SAML branch lights up once `sso_configs` carries an
email-domain mapping.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.core.auth import AuthMiddleware
from app.domain.sessions import web as _sessions_web  # noqa: F401


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    from app.core.webserver import mount_specs  # noqa: PLC0415

    mount_specs(app, only={"sessions"})
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_discover_returns_github_for_known_email_format() -> None:
    async with _client() as c:
        r = await c.get("/api/auth/sso/discover", params={"email": "alice@example.com"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "github"


@pytest.mark.asyncio
async def test_discover_rejects_empty_email() -> None:
    async with _client() as c:
        r = await c.get("/api/auth/sso/discover", params={"email": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_discover_rejects_email_without_at_sign() -> None:
    async with _client() as c:
        r = await c.get("/api/auth/sso/discover", params={"email": "notanemail"})
    assert r.status_code == 422
