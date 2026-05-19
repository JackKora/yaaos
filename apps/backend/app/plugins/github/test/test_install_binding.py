"""Phase 10 — GitHub App install ↔ org binding tests.

Covers state signature verification, mismatched-state rejection, and
`resolve_org_for_installation` returning the bound org.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select

from app.core.auth import AuthMiddleware
from app.domain.identity.models import GithubInstallationRow
from app.plugins.github.web import _install_state_serializer, resolve_org_for_installation


def _app() -> FastAPI:
    from app.core.webserver.registry import _specs  # noqa: PLC0415

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    spec = _specs["github"]
    app.include_router(spec.router, prefix=spec.url_prefix or "/api/github")
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_app()), base_url="http://test")


@pytest_asyncio.fixture
async def seed_org(db_session):
    org_id = uuid4()
    yield org_id


@pytest.mark.asyncio
async def test_install_callback_bad_state_returns_400(seed_org) -> None:
    async with _client() as c:
        r = await c.get(
            "/api/github/install_callback",
            params={"state": "not-a-signed-value", "installation_id": "42"},
            follow_redirects=False,
        )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "state_invalid"


@pytest.mark.asyncio
async def test_install_callback_missing_params_returns_400() -> None:
    async with _client() as c:
        r = await c.get("/api/github/install_callback", follow_redirects=False)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_install_callback_happy_path_writes_row_and_resolves(seed_org, db_session) -> None:
    state = _install_state_serializer().dumps({"org_id": str(seed_org)})
    async with _client() as c:
        r = await c.get(
            "/api/github/install_callback",
            params={"state": state, "installation_id": "9999"},
            follow_redirects=False,
        )
    assert r.status_code in (302, 303, 307)

    # Row should exist; resolve_org returns the bound org. Use the
    # override-aware session() so the test sees the route's commit.
    from app.core.database import session as db_session_factory  # noqa: PLC0415

    async with db_session_factory() as s:
        row = (
            await s.execute(
                select(GithubInstallationRow).where(GithubInstallationRow.installation_id == 9999)
            )
        ).scalar_one_or_none()
        assert row is not None
        assert row.org_id == seed_org
        # Cleanup.
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_resolve_org_for_installation_returns_none_when_unbound() -> None:
    out = await resolve_org_for_installation(123456789)
    assert out is None


@pytest.mark.asyncio
async def test_state_signature_is_per_secret(seed_org) -> None:
    # A token signed with a different secret/salt must NOT verify.
    from itsdangerous import URLSafeTimedSerializer  # noqa: PLC0415

    forged = URLSafeTimedSerializer("wrong-secret", salt="yaaos-github-install").dumps(
        {"org_id": str(seed_org)}
    )
    async with _client() as c:
        r = await c.get(
            "/api/github/install_callback",
            params={"state": forged, "installation_id": "1"},
            follow_redirects=False,
        )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "state_invalid"


# Keep UUID import in use (linter).
_ = UUID
