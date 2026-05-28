"""Service tests: `notifications.handle_ticket_status_change` task handler.

Three scenarios:
1. Handler called with two recipients writes two notification rows.
2. Calling the handler twice with identical args writes exactly two rows
   (idempotency guaranteed by `service.record`'s dedup on (user_id, type, ticket_id)).
3. Handler invoked via the outbox drain path (enqueue → drain → task body)
   writes the same notification rows — verifying the durability path.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.core.identity import repository as identity_repo
from app.core.tasks import drain_once, enqueue
from app.domain.notifications import handle_ticket_status_change
from app.domain.notifications.models import NotificationRow
from app.domain.notifications.tasks import _handle_ticket_status_change
from app.domain.orgs import Role
from app.domain.orgs import repository as orgs_repo


@pytest_asyncio.fixture
async def seeded(db_session):
    alice = await identity_repo.insert_user(db_session, display_name="Alice")
    bob = await identity_repo.insert_user(db_session, display_name="Bob")
    org = await orgs_repo.insert_org(db_session, slug="task-org", display_name="TaskOrg")
    await orgs_repo.insert_membership(
        db_session, user_id=alice.id, org_id=org.id, role=Role.BUILDER, handle="alice"
    )
    await orgs_repo.insert_membership(
        db_session, user_id=bob.id, org_id=org.id, role=Role.BUILDER, handle="bob"
    )

    ticket_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO tickets (id, org_id, source, source_external_id, title, status, plugin_id,"
            " repo_external_id) VALUES (:id, :org_id, 'github_pr', 'x/y#42', 'Fix the flake',"
            " 'running', 'github', 'x/y')"
        ),
        {"id": ticket_id, "org_id": org.id},
    )
    await db_session.commit()
    yield {"alice": alice, "bob": bob, "org": org, "ticket_id": ticket_id}


@pytest.mark.asyncio
@pytest.mark.service
async def test_handle_ticket_status_change_records_per_member(seeded, db_session) -> None:
    """Handler with two recipients writes exactly two notification rows."""
    alice_id = seeded["alice"].id
    bob_id = seeded["bob"].id
    ticket_id = seeded["ticket_id"]
    org_id = seeded["org"].id

    await _handle_ticket_status_change(
        ticket_id=ticket_id,
        member_user_ids=[alice_id, bob_id],
        org_id=org_id,
        new_status="done",
    )

    rows = (
        (await db_session.execute(select(NotificationRow).where(NotificationRow.ticket_id == ticket_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert {r.user_id for r in rows} == {alice_id, bob_id}
    for r in rows:
        assert r.type == "ticket_completed"
        assert r.title == "Review complete"
        assert r.body == "Fix the flake"
        assert r.org_id == org_id


@pytest.mark.asyncio
@pytest.mark.service
async def test_handle_ticket_status_change_is_idempotent_on_redelivery(seeded, db_session) -> None:
    """Calling the handler twice with identical args yields exactly two rows, not four."""
    alice_id = seeded["alice"].id
    bob_id = seeded["bob"].id
    ticket_id = seeded["ticket_id"]
    org_id = seeded["org"].id

    kwargs = dict(
        ticket_id=ticket_id,
        member_user_ids=[alice_id, bob_id],
        org_id=org_id,
        new_status="hitl",
    )
    await _handle_ticket_status_change(**kwargs)
    await _handle_ticket_status_change(**kwargs)

    rows = (
        (await db_session.execute(select(NotificationRow).where(NotificationRow.ticket_id == ticket_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2, "idempotent: second call must not duplicate rows"
    assert {r.type for r in rows} == {"hitl_waiting"}


@pytest.mark.asyncio
@pytest.mark.service
async def test_handle_ticket_status_change_durability_via_outbox(seeded, db_session) -> None:
    """Task survives the outbox drain: enqueue writes an outbox row; drain
    dispatches it via a local dispatcher; the task body executes and writes
    notification rows — proving the atomic-in-session durability path.

    Uses a local dispatcher rather than the production taskiq broker to stay
    within `core/tasks`' public interface (no private drain submodule
    imports). The dispatcher routes `taskiq_enqueue` payloads directly to
    `_handle_ticket_status_change`, mirroring what the production worker does.
    """
    alice_id = seeded["alice"].id
    bob_id = seeded["bob"].id
    ticket_id = seeded["ticket_id"]
    org_id = seeded["org"].id

    # Enqueue via the outbox — atomic with the session.
    await enqueue(
        handle_ticket_status_change,
        args={
            "ticket_id": str(ticket_id),
            "member_user_ids": [str(alice_id), str(bob_id)],
            "org_id": str(org_id),
            "new_status": "failed",
        },
        metadata={"org_id": str(org_id)},
        session=db_session,
    )
    await db_session.commit()

    # Local dispatcher: routes the outbox payload to the task body directly,
    # coercing string UUIDs back to UUID objects as the real worker would.
    async def _dispatcher(kind: str, payload: dict[str, Any]) -> None:
        assert kind == "taskiq_enqueue"
        args = payload["args"]
        await _handle_ticket_status_change(
            ticket_id=UUID(args["ticket_id"]),
            member_user_ids=[UUID(u) for u in args["member_user_ids"]],
            org_id=UUID(args["org_id"]),
            new_status=args["new_status"],
        )

    delivered = await drain_once(db_session, dispatcher=_dispatcher)
    await db_session.commit()

    assert delivered == 1, "drain must have dispatched the outbox row"

    rows = (
        (await db_session.execute(select(NotificationRow).where(NotificationRow.ticket_id == ticket_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert {r.user_id for r in rows} == {alice_id, bob_id}
    assert {r.type for r in rows} == {"ticket_failed"}
