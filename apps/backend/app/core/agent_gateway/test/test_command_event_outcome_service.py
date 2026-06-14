"""HTTP-layer service tests for the CommandEventAck outcome body on
POST /api/v1/commands/{id}/events.

The endpoint always returns 200 with `{"command_event_outcome": "<value>"}`.
These tests assert the two possible outcomes at the HTTP layer and verify that
the backend stamps `command_event.outcome` on the FastAPI request span.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.core.agent_gateway import (
    AuthBlock,
    ProvisionWorkspaceCommand,
    RepoRef,
    bearers,
    enqueue_command,
)
from app.core.agent_gateway.models import WorkspaceAgentRow
from app.core.agent_gateway.types import AgentEvent, AgentEventKind
from app.domain.orgs import repository as orgs_repo
from app.testing.observability import span_capture
from app.testing.seed import seed_workspace

# ── App factory ───────────────────────────────────────────────────────────


def _app() -> FastAPI:
    app = FastAPI()
    from app.core.webserver import mount_specs  # noqa: PLC0415

    mount_specs(app, only={"agent_gateway"})
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_app()), base_url="http://test")


# ── Shared setup ─────────────────────────────────────────────────────────


async def _insert_agent(db_session, org_id: UUID) -> UUID:
    agent = WorkspaceAgentRow(
        id=uuid4(),
        org_id=org_id,
        instance_id=f"test-task-{uuid4().hex[:8]}",
        iam_arn=f"arn:aws:iam::123456789012:role/test-{uuid4().hex[:6]}",
        version="0.0.1",
        state="reachable",
    )
    db_session.add(agent)
    await db_session.commit()
    return agent.id


async def _setup_agent_with_bearer(db_session):
    """Insert one org + one agent; issue a bearer. Returns (agent_id, org_id, token)."""
    org = await orgs_repo.insert_org(db_session, slug=f"outcome-{uuid4().hex[:6]}")
    org.registered_iam_arn = f"arn:aws:iam::123456789012:role/test-{uuid4().hex[:6]}"
    org.aws_region = "us-east-1"
    await db_session.commit()

    agent_id = await _insert_agent(db_session, org.org_id)
    plaintext, _ = await bearers.issue(
        agent_id=agent_id, org_id=org.org_id, session=db_session, source_ip="127.0.0.1"
    )
    await db_session.commit()
    return agent_id, org.org_id, plaintext


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate():
    bearers.set_verify_override(None)
    yield
    bearers.set_verify_override(None)


@pytest.mark.asyncio
@pytest.mark.service
async def test_command_event_stale_claim_returns_200_with_outcome(db_session) -> None:
    """A stale command_id (no matching agent_commands row) returns 200 with
    `command_event_outcome = stale_claim_dropped` — not 410."""
    agent_id, org_id, token = await _setup_agent_with_bearer(db_session)
    del agent_id, org_id
    cmd_id = uuid4()

    async with _client() as c:
        resp = await c.post(
            f"/api/v1/commands/{cmd_id}/events",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "command_id": str(cmd_id),
                "kind": "completed_success",
                "reported_at": datetime.now(UTC).isoformat(),
                "traceparent": "00-aabb-1122-01",
            },
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"command_event_outcome": "stale_claim_dropped"}


@pytest.mark.asyncio
@pytest.mark.service
async def test_command_event_recorded_returns_200_with_outcome(db_session) -> None:
    """A valid event for an existing command returns 200 with
    `command_event_outcome = event_recorded`."""
    agent_id, org_id, token = await _setup_agent_with_bearer(db_session)
    cmd_id = uuid4()
    wfx_id = uuid4()

    ws_id = await seed_workspace(
        org_id=org_id,
        provider_id="remote_agent",
        sha="deadbeef",
        current_command_id=cmd_id,
        agent_id=agent_id,
        caller_session=db_session,
    )
    provision = ProvisionWorkspaceCommand(
        command_id=cmd_id,
        workspace_id=UUID(ws_id),
        traceparent="00-aabbccdd-1122-01",
        repo=RepoRef(
            plugin_id="github",
            external_id="123",
            clone_url="https://github.com/me/repo.git",
            head_sha="deadbeef",
        ),
        history=1,
        auth=AuthBlock(kind="github_installation", token="redacted"),
        ttl_seconds=600,
        max_idle_seconds=600,
    )
    await enqueue_command(
        org_id=org_id,
        command=provision,
        session=db_session,
        workflow_execution_id=wfx_id,
    )
    await db_session.commit()

    async with _client() as c:
        resp = await c.post(
            f"/api/v1/commands/{cmd_id}/events",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "command_id": str(cmd_id),
                "kind": "completed_success",
                "reported_at": datetime.now(UTC).isoformat(),
                "traceparent": "00-aabb-1122-01",
            },
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"command_event_outcome": "event_recorded"}


@pytest.mark.asyncio
@pytest.mark.service
async def test_command_event_span_carries_outcome_attribute(db_session) -> None:
    """The active span carries `command_event.outcome` after the endpoint handler runs.

    `web.py` calls `trace.get_current_span().set_attribute("command_event.outcome", outcome)`.
    We open an explicit test span so the attribute lands somewhere queryable.
    """
    from opentelemetry import trace as otel_trace  # noqa: PLC0415

    agent_id, org_id, token = await _setup_agent_with_bearer(db_session)
    del agent_id, org_id

    from app.core.agent_gateway.web import post_command_event  # noqa: PLC0415

    cmd_id = uuid4()
    event = AgentEvent(
        command_id=cmd_id,
        kind=AgentEventKind.COMPLETED_SUCCESS,
        reported_at=datetime.now(UTC),
        traceparent="00-aabb-1122-01",
    )
    bearer_ctx = await bearers.verify(token)
    assert bearer_ctx is not None

    with span_capture() as exporter:
        tracer = otel_trace.get_tracer(__name__)
        with tracer.start_as_current_span("test.post_command_event"):
            resp = await post_command_event(
                event=event,
                command_id=cmd_id,
                agent=bearer_ctx,
            )

    assert resp.status_code == 200
    spans = exporter.get_finished_spans()
    outcome_attrs = [
        dict(s.attributes or {}).get("command_event.outcome")
        for s in spans
        if dict(s.attributes or {}).get("command_event.outcome") is not None
    ]
    assert outcome_attrs, f"no span carries command_event.outcome; spans: {[s.name for s in spans]}"
    assert "stale_claim_dropped" in outcome_attrs, f"expected stale_claim_dropped in {outcome_attrs}"
