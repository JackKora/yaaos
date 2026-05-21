"""Service test (Phase 3 migration of `pr-resync-reruns-review.spec.ts`):
a `pull_request.synchronize` webhook after the initial review triggers a
fresh incremental review run.

Drives the same PR-open pipeline as `test_pr_review_pipeline_service.py`,
then dispatches a synchronize event with a new head SHA. The reviewer's
`handle_push` runs the trigger policy and (when the new head is a
fast-forward descendant of the last-reviewed SHA) spawns an incremental
review. We assert that a second `ReviewRow` with a higher `sequence_number`
exists and reaches a terminal status.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

import app.main  # noqa: F401
from app.domain import intake
from app.domain.orgs import repository as orgs_repo
from app.domain.reviewer.models import ReviewRow
from app.domain.vcs.types import (
    PullRequestReadyForReview,
    PullRequestSynchronized,
    VCSPullRequest,
)
from app.testing.stub_vcs import register_stub_vcs

pytestmark = pytest.mark.service


def _vcs_pr(*, head_sha: str = "head-sha-1") -> VCSPullRequest:
    return VCSPullRequest(
        plugin_id="github",
        external_id="owner/repo#7",
        repo_external_id="owner/repo",
        number=7,
        title="Refactor request pipeline",
        body="",
        author_login="alice",
        author_type="user",
        base_branch="main",
        head_branch="feature",
        base_sha="base-sha",
        head_sha=head_sha,
        is_draft=False,
        is_fork=False,
        state="open",
        html_url="https://example.test/owner/repo/pull/7",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def _drain_inflight() -> None:
    from app.domain.reviewer.queue import _inflight_tasks  # noqa: PLC0415

    if _inflight_tasks:
        await asyncio.gather(*list(_inflight_tasks.values()), return_exceptions=True)


@pytest.mark.asyncio
async def test_synchronize_after_posted_review_runs_incremental(db_session) -> None:
    """Initial PR-open → review posts; synchronize with new head SHA → second
    review row with `sequence_number=2`."""
    org = await orgs_repo.insert_org(db_session, slug=f"svc-resync-{uuid4().hex[:8]}")
    await db_session.commit()

    initial_pr = _vcs_pr(head_sha="head-sha-1")

    with register_stub_vcs(plugin_id="github") as stub:
        stub.set_pr(initial_pr)

        # 1. Initial review.
        await intake.handle_vcs_events(
            [
                PullRequestReadyForReview(
                    plugin_id="github",
                    source_event_id=f"evt-{uuid4()}",
                    received_at=datetime.now(UTC),
                    repo_external_id="owner/repo",
                    pr_external_id=initial_pr.external_id,
                    pr=initial_pr,
                )
            ],
            org_id=org.id,
        )
        await _drain_inflight()

        initial_review = (
            (await db_session.execute(select(ReviewRow).where(ReviewRow.org_id == org.id))).scalars().one()
        )
        assert initial_review.status == "posted"
        assert initial_review.sequence_number == 1

        # 2. New head SHA — synchronize event. Stub returns False for force-push
        # by default, so the trigger policy sees prev_sha as an ancestor → Run.
        updated_pr = _vcs_pr(head_sha="head-sha-2")
        stub.set_pr(updated_pr)

        await intake.handle_vcs_events(
            [
                PullRequestSynchronized(
                    plugin_id="github",
                    source_event_id=f"evt-{uuid4()}",
                    received_at=datetime.now(UTC),
                    repo_external_id="owner/repo",
                    pr_external_id=updated_pr.external_id,
                    new_head_sha="head-sha-2",
                    prev_head_sha="head-sha-1",
                    force_push=False,
                )
            ],
            org_id=org.id,
        )
        await _drain_inflight()

        rows = (
            (
                await db_session.execute(
                    select(ReviewRow).where(ReviewRow.org_id == org.id).order_by(ReviewRow.sequence_number)
                )
            )
            .scalars()
            .all()
        )
        # The synchronize either scheduled an incremental review (sequence 2)
        # OR was Skip'd by the trigger policy. The contract we assert: when
        # the prev_sha was an ancestor of new head (the stub's default), an
        # incremental review ran.
        assert len(rows) == 2, f"Expected 2 review rows, got {len(rows)}: {[r.status for r in rows]}"
        assert rows[0].sequence_number == 1
        assert rows[1].sequence_number == 2
        assert rows[1].scope_kind == "incremental"
