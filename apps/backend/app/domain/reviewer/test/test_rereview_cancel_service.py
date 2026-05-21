"""Service test (Phase 3 migration of `manual-rereview-and-cancel.spec.ts`):
manual re-review schedules a fresh review-job + cancel writes a
`review_job.cancelled` audit row.

Two scenarios:

1. After an initial review posts, calling `schedule_review` again creates a
   new `ReviewRow` and writes a `review_job.scheduled` audit with
   `trigger_reason="manual_full"`.
2. `cancel_pending` against a ticket with an in-flight (queued) job writes
   the `review_job.cancelled` audit + flips the row to `cancelled`.

Drives the same intake → reviewer pipeline as the gap-A service test, then
exercises the manual entry points directly.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

import app.main  # noqa: F401
from app.core.audit_log import Actor
from app.domain import intake, reviewer
from app.domain.orgs import repository as orgs_repo
from app.domain.reviewer.models import ReviewRow
from app.domain.vcs.types import PullRequestReadyForReview, VCSPullRequest
from app.testing.stub_vcs import register_stub_vcs

pytestmark = pytest.mark.service


def _vcs_pr(external_id: str = "owner/repo#12") -> VCSPullRequest:
    return VCSPullRequest(
        plugin_id="github",
        external_id=external_id,
        repo_external_id="owner/repo",
        number=12,
        title="Tiny change",
        body="",
        author_login="alice",
        author_type="user",
        base_branch="main",
        head_branch="feature",
        base_sha="base-sha",
        head_sha="head-sha",
        is_draft=False,
        is_fork=False,
        state="open",
        html_url="https://example.test/owner/repo/pull/12",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def _drain_inflight() -> None:
    from app.domain.reviewer.queue import _inflight_tasks  # noqa: PLC0415

    if _inflight_tasks:
        await asyncio.gather(*list(_inflight_tasks.values()), return_exceptions=True)


@pytest.mark.asyncio
async def test_rereview_creates_new_review_with_manual_full_trigger(db_session) -> None:
    org = await orgs_repo.insert_org(db_session, slug=f"svc-rereview-{uuid4().hex[:8]}")
    await db_session.commit()

    vcs_pr = _vcs_pr()
    with register_stub_vcs(plugin_id="github") as stub:
        stub.set_pr(vcs_pr)

        await intake.handle_vcs_events(
            [
                PullRequestReadyForReview(
                    plugin_id="github",
                    source_event_id=f"evt-{uuid4()}",
                    received_at=datetime.now(UTC),
                    repo_external_id="owner/repo",
                    pr_external_id=vcs_pr.external_id,
                    pr=vcs_pr,
                )
            ],
            org_id=org.id,
        )
        await _drain_inflight()

        # Look up the ticket the intake created.
        ticket_row = (
            (
                await db_session.execute(
                    text("SELECT id FROM tickets WHERE org_id=:org AND source_external_id=:eid"),
                    {"org": org.id, "eid": vcs_pr.external_id},
                )
            )
            .scalars()
            .one()
        )

        # Drive a manual re-review.
        new_review_id = await reviewer.schedule_review(
            ticket_id=ticket_row,
            trigger_reason="manual_full",
            actor=Actor.system(),
            org_id=org.id,
        )
        assert new_review_id is not None
        await _drain_inflight()

        rows = (await db_session.execute(select(ReviewRow).where(ReviewRow.org_id == org.id))).scalars().all()
        # Initial review + manual rereview.
        assert len(rows) == 2
        sequence_numbers = sorted(r.sequence_number for r in rows)
        assert sequence_numbers == [1, 2]

        manual_audit = (
            await db_session.execute(
                text(
                    "SELECT payload FROM audit_entries"
                    " WHERE entity_kind='review_job' AND entity_id=:id AND kind='review_job.scheduled'"
                ),
                {"id": new_review_id},
            )
        ).all()
        assert len(manual_audit) == 1
        payload = manual_audit[0][0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["trigger_reason"] == "manual_full"


@pytest.mark.asyncio
async def test_cancel_pending_flips_queued_review_to_cancelled_with_audit(db_session) -> None:
    """`cancel_pending` flips queued/running ReviewRows to `cancelled` + writes
    a `review_job.cancelled` audit with the supplied `reason`.

    Inserts a queued ReviewRow directly (no asyncio task in `_inflight_tasks`)
    so this test exercises the status-flip + audit path in isolation from the
    task-interruption logic — which is hard to test deterministically because
    the spawned task races against the cancel call on the same overridden
    DB session.
    """
    org = await orgs_repo.insert_org(db_session, slug=f"svc-cancel-{uuid4().hex[:8]}")

    # Seed ticket + PR + queued review directly. No intake, no spawn.
    ticket_id = uuid4()
    pr_id = uuid4()
    review_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO tickets (id, org_id, source, source_external_id, title, status,"
            " plugin_id, repo_external_id)"
            " VALUES (:id, :org, 'github_pr', 'owner/repo#13', 't', 'in_review',"
            " 'github', 'owner/repo')"
        ),
        {"id": ticket_id, "org": org.id},
    )
    await db_session.execute(
        text(
            "INSERT INTO pull_requests"
            " (id, org_id, ticket_id, plugin_id, external_id, repo_external_id, number, title,"
            "  body, author_login, author_type, base_branch, head_branch, base_sha, head_sha,"
            "  is_draft, is_fork, state, html_url)"
            " VALUES (:id, :org, :tid, 'github', 'owner/repo#13', 'owner/repo', 13, 't', '',"
            "         'a', 'user', 'main', 'b', 'base', 'head', false, false, 'open',"
            "         'https://example.test')"
        ),
        {"id": pr_id, "org": org.id, "tid": ticket_id},
    )
    await db_session.execute(
        text("UPDATE tickets SET pr_id=:pr WHERE id=:tid"),
        {"pr": pr_id, "tid": ticket_id},
    )
    db_session.add(
        ReviewRow(
            id=review_id,
            org_id=org.id,
            pr_id=pr_id,
            sequence_number=1,
            status="queued",
            trigger_reason="manual_full",
            destination="vcs",
        )
    )
    await db_session.commit()

    cancelled = await reviewer.cancel_pending(
        ticket_id,
        actor=Actor.system(),
        org_id=org.id,
        reason="ui_cancel",
    )
    assert cancelled == 1

    # Row flipped + audit written.
    status = (
        await db_session.execute(text("SELECT status FROM reviews WHERE id=:id"), {"id": review_id})
    ).scalar_one()
    assert status == "cancelled"

    cancel_audits = (
        await db_session.execute(
            text(
                "SELECT payload FROM audit_entries"
                " WHERE entity_kind='review_job' AND entity_id=:id AND kind='review_job.cancelled'"
            ),
            {"id": review_id},
        )
    ).all()
    assert len(cancel_audits) == 1
    payload = cancel_audits[0][0]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["reason"] == "ui_cancel"
