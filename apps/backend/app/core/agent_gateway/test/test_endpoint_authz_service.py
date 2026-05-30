"""Service tests: per-endpoint identity authz on the bearer HTTP endpoints.

`heartbeat` and `claim_command` bind on a path `agent_id`. The bearer
resolves to its own `agent.agent_id`. A bearer for agent A must NOT be
able to address agent B's row (heartbeat) or queue (claim) inside the
same org — that is the IDOR these tests guard. Mirrors the WebSocket
handler's `ctx.agent_id != agent_id → 4403` precedent.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.core.agent_gateway import bearers
from app.core.agent_gateway.models import WorkspaceAgentRow
from app.domain.orgs import repository as orgs_repo

# ── Helpers ──────────────────────────────────────────────────────────────


def _app() -> FastAPI:
    app = FastAPI()
    from app.core.webserver import mount_specs  # noqa: PLC0415

    mount_specs(app, only={"agent_gateway"})
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_app()), base_url="http://test")


async def _insert_agent(db_session, org_id: UUID) -> UUID:
    agent = WorkspaceAgentRow(
        id=uuid4(),
        org_id=org_id,
        agent_pod_id=uuid4(),
        iam_arn=f"arn:aws:iam::123456789012:role/test-{uuid4().hex[:6]}",
        version="0.0.1",
        state="reachable",
    )
    db_session.add(agent)
    await db_session.commit()
    return agent.id


async def _two_agents_one_org(db_session) -> tuple[UUID, UUID, str]:
    """Insert one org with two agents; issue a bearer for agent A.

    Returns (agent_a_id, agent_b_id, bearer_for_a).
    """
    org = await orgs_repo.insert_org(db_session, slug=f"authz-{uuid4().hex[:6]}")
    org.registered_iam_arn = f"arn:aws:iam::123456789012:role/test-{uuid4().hex[:6]}"
    org.aws_region = "us-east-1"
    await db_session.commit()

    agent_a = await _insert_agent(db_session, org.org_id)
    agent_b = await _insert_agent(db_session, org.org_id)

    plaintext, _ = await bearers.issue(
        agent_id=agent_a, org_id=org.org_id, session=db_session, source_ip="127.0.0.1"
    )
    await db_session.commit()
    return agent_a, agent_b, plaintext


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate():
    bearers.set_verify_override(None)
    yield
    bearers.set_verify_override(None)


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.service
async def test_heartbeat_rejects_foreign_agent_id(db_session) -> None:
    """A bearer for agent A bumping agent B's heartbeat row → 403."""
    _agent_a, agent_b, token = await _two_agents_one_org(db_session)
    async with _client() as c:
        resp = await c.post(
            f"/api/v1/agents/{agent_b}/heartbeat",
            headers={"Authorization": f"Bearer {token}"},
            json={"workspaces": [], "reported_at": "2026-01-01T00:00:00Z"},
        )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"]["error"] == "forbidden"


@pytest.mark.asyncio
@pytest.mark.service
async def test_claim_rejects_foreign_agent_id(db_session) -> None:
    """A bearer for agent A claiming against agent B's queue → 403."""
    _agent_a, agent_b, token = await _two_agents_one_org(db_session)
    async with _client() as c:
        resp = await c.post(
            f"/api/v1/agents/{agent_b}/commands/claim",
            headers={"Authorization": f"Bearer {token}"},
            json={"wait_seconds": 0, "lifecycle": "unconfigured"},
        )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"]["error"] == "forbidden"


@pytest.mark.asyncio
@pytest.mark.service
async def test_heartbeat_allows_own_agent_id(db_session) -> None:
    """The happy path — a bearer addressing its own agent_id still succeeds."""
    agent_a, _agent_b, token = await _two_agents_one_org(db_session)
    async with _client() as c:
        resp = await c.post(
            f"/api/v1/agents/{agent_a}/heartbeat",
            headers={"Authorization": f"Bearer {token}"},
            json={"workspaces": [], "reported_at": "2026-01-01T00:00:00Z"},
        )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
@pytest.mark.service
async def test_claim_allows_own_agent_id(db_session) -> None:
    """The happy path — a bearer claiming against its own queue still succeeds
    (204 when nothing is configured-eligible at wait_seconds=0 is fine; an
    unconfigured claim returns a ConfigUpdate at 200)."""
    agent_a, _agent_b, token = await _two_agents_one_org(db_session)
    async with _client() as c:
        resp = await c.post(
            f"/api/v1/agents/{agent_a}/commands/claim",
            headers={"Authorization": f"Bearer {token}"},
            json={"wait_seconds": 0, "lifecycle": "unconfigured"},
        )
    assert resp.status_code == 200, resp.text
