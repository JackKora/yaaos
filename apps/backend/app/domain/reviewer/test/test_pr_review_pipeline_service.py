"""Service test (Phase 2 gap A): intake → reviewer → workspace → coding_agent → vcs.post_review.

Drives `domain.intake.handle_vcs_events` with a `PullRequestReadyForReview`
event end-to-end, in-process, against:
- real Postgres via the `db_session` fixture (transactional rollback)
- the `StubVCSPlugin` registered for plugin_id="github"
- the testing-layer `stub_coding_agent` + `stub_workspace` providers (wrapped
  at bootstrap when `YAAOS_CODING_AGENT_STUB=1`, which conftest sets)

Asserts the durable state production reads: `ReviewRow.status="posted"`,
the three audit kinds along the path, and the stub vcs's recorded
`post_review` call.

The github plugin can't be driven in-process without a stub — `fetch_pr` /
`fetch_diff` / `post_review` hit `GITHUB_API_BASE_URL` which only resolves
inside the docker test stack. `register_stub_vcs(plugin_id="github")` swaps
the real plugin for a stub that returns canned data.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

import app.main  # noqa: F401  — triggers stub_coding_agent + stub_workspace wraps
from app.domain import intake
from app.domain.orgs import repository as orgs_repo
from app.domain.reviewer.models import ReviewRow
from app.domain.vcs.types import PullRequestReadyForReview, VCSPullRequest
from app.testing.stub_vcs import register_stub_vcs

pytestmark = pytest.mark.service


def _make_vcs_pr() -> VCSPullRequest:
    return VCSPullRequest(
        plugin_id="github",
        external_id="owner/repo#42",
        repo_external_id="owner/repo",
        number=42,
        title="Stub PR for pipeline test",
        body="Body.",
        author_login="alice",
        author_type="user",
        base_branch="main",
        head_branch="feature/x",
        base_sha="base-sha-1",
        head_sha="head-sha-1",
        is_draft=False,
        is_fork=False,
        state="open",
        html_url="https://example.test/owner/repo/pull/42",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def _wait_for_terminal_review(db_session, *, org_id, timeout_seconds: float = 10.0) -> ReviewRow:
    """Poll the test session for a ReviewRow in a terminal status. The spawned
    review task uses the same overridden session, so writes are visible here
    once the inner SAVEPOINT releases on `commit()`."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        row = (
            (await db_session.execute(select(ReviewRow).where(ReviewRow.org_id == org_id))).scalars().first()
        )
        if row is not None and row.status in {"posted", "failed", "skipped", "cancelled"}:
            return row
        await asyncio.sleep(0.05)
    raise TimeoutError(f"Review never reached terminal state for org {org_id}")


@pytest.mark.asyncio
async def test_pr_ready_drives_full_pipeline_to_posted(db_session) -> None:
    """`PullRequestReadyForReview` event → intake → reviewer.schedule_review →
    spawned task runs through workspace + coding_agent + vcs.post_review →
    `ReviewRow.status="posted"` + audit chain + stub recorded the post.
    """
    from app.domain.reviewer.queue import _inflight_tasks  # noqa: PLC0415

    org = await orgs_repo.insert_org(db_session, slug=f"svc-pipe-{uuid4().hex[:8]}")
    await db_session.commit()

    vcs_pr = _make_vcs_pr()

    with register_stub_vcs(plugin_id="github") as stub:
        stub.set_pr(vcs_pr)

        event = PullRequestReadyForReview(
            plugin_id="github",
            source_event_id=f"evt-{uuid4()}",
            received_at=datetime.now(UTC),
            repo_external_id="owner/repo",
            pr_external_id=vcs_pr.external_id,
            pr=vcs_pr,
        )
        await intake.handle_vcs_events([event], org_id=org.id)

        # The spawned review task is in `_inflight_tasks`. Await it directly so
        # we serialize with its writes — the test's transactional session is
        # shared with the spawned coro via the global override, and concurrent
        # use would race.
        if _inflight_tasks:
            tasks = list(_inflight_tasks.values())
            await asyncio.gather(*tasks, return_exceptions=True)

        review = await _wait_for_terminal_review(db_session, org_id=org.id)

        assert review.status == "posted", f"Expected posted, got {review.status}: {review.error_message}"

        # Audit chain along the path.
        kinds = [
            r[0]
            for r in (
                await db_session.execute(
                    text(
                        "SELECT kind FROM audit_entries"
                        " WHERE entity_kind='review_job' AND entity_id=:id"
                        " ORDER BY created_at"
                    ),
                    {"id": review.id},
                )
            ).all()
        ]
        assert "review_job.scheduled" in kinds
        assert "review_job.prompt_sent" in kinds
        assert "review_job.posted" in kinds

        # Stub VCS recorded the review post.
        assert len(stub.posted_reviews) == 1
        posted_external_id, posted_review = stub.posted_reviews[0]
        assert posted_external_id == vcs_pr.external_id
        assert posted_review.agent_tag == "yaaos"
        # The stub coding agent emits one synthetic finding anchored to
        # src/example.ts; the diff returned by the stub VCS includes that
        # file, so admission keeps it.
        assert len(posted_review.findings) == 1
