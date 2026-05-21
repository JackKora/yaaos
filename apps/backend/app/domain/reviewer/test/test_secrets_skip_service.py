"""Service test (Phase 3 migration of `secrets-refuse-to-review.spec.ts`):
a PR whose diff contains a secret pattern → review is skipped with
`skip_reason="secrets_detected"` + the warning Review is posted via the VCS.

Drives the full intake → reviewer pipeline (the secrets pre-flight runs
inside `_run_review_job_inner`) with a stub VCS that returns a
secret-containing diff. The reviewer's `_detect_secrets` matches the AWS
access-key pattern and short-circuits before the coding-agent invocation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

import app.main  # noqa: F401
from app.domain import intake
from app.domain.orgs import repository as orgs_repo
from app.domain.reviewer.models import ReviewRow
from app.domain.vcs.types import (
    Diff,
    FileSummary,
    PullRequestReadyForReview,
    VCSPullRequest,
)
from app.testing.stub_vcs import register_stub_vcs

pytestmark = pytest.mark.service


def _vcs_pr() -> VCSPullRequest:
    return VCSPullRequest(
        plugin_id="github",
        external_id="owner/repo#99",
        repo_external_id="owner/repo",
        number=99,
        title="Add env file with credentials",
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
        html_url="https://example.test/owner/repo/pull/99",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def _drain_inflight() -> None:
    from app.domain.reviewer.queue import _inflight_tasks  # noqa: PLC0415

    if _inflight_tasks:
        await asyncio.gather(*list(_inflight_tasks.values()), return_exceptions=True)


@pytest.mark.asyncio
async def test_pr_with_aws_key_in_diff_is_skipped_with_warning_posted(db_session) -> None:
    org = await orgs_repo.insert_org(db_session, slug=f"svc-secrets-{uuid4().hex[:8]}")
    await db_session.commit()

    vcs_pr = _vcs_pr()

    with register_stub_vcs(plugin_id="github") as stub:
        stub.set_pr(vcs_pr)
        stub.set_diff(
            vcs_pr.external_id,
            Diff(
                raw=(
                    "diff --git a/.env b/.env\n"
                    "index 0000000..1111111 100644\n"
                    "--- a/.env\n"
                    "+++ b/.env\n"
                    "@@ -0,0 +1,1 @@\n"
                    "+AWS_KEY=AKIAIOSFODNN7EXAMPLE\n"
                ),
                files=[FileSummary(path=".env", status="modified", additions=1, deletions=0)],
            ),
        )

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

        review = (
            (await db_session.execute(select(ReviewRow).where(ReviewRow.org_id == org.id))).scalars().one()
        )
        assert review.status == "skipped"
        assert review.skip_reason == "secrets_detected"

        # The reviewer posted the warning Review to the stub VCS before
        # short-circuiting. Body mentions the rule.
        assert len(stub.posted_reviews) == 1
        external_id, posted = stub.posted_reviews[0]
        assert external_id == vcs_pr.external_id
        assert posted.summary_body is not None
        assert "secret" in posted.summary_body.lower()

        # No `review_job.posted` audit row (we skipped). Should see
        # `review_job.skipped` instead.
        kinds = [
            r[0]
            for r in (
                await db_session.execute(
                    text("SELECT kind FROM audit_entries WHERE entity_kind='review_job' AND entity_id=:id"),
                    {"id": review.id},
                )
            ).all()
        ]
        assert "review_job.skipped" in kinds
        assert "review_job.posted" not in kinds
