"""Service test (Phase 3 migration of `lesson-applied-next-review.spec.ts`):
a pre-existing repo-scoped lesson shows up in the `review_job.prompt_sent`
audit payload's `lessons_count` + `lessons_applied` fields.

Drives the same full PR-open pipeline as `test_pr_review_pipeline_service.py`
but with a seeded lesson on the repo. The reviewer queue's prompt-assembly
step reads lessons via `memory.list_for_repo(repo_external_id, ...)` and
records the count + ids on the `review_job.prompt_sent` audit row.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

import app.main  # noqa: F401  — triggers stub bootstrap wraps
from app.core.audit_log import Actor
from app.domain import intake, memory
from app.domain.orgs import repository as orgs_repo
from app.domain.reviewer.models import ReviewRow
from app.domain.vcs.types import PullRequestReadyForReview, VCSPullRequest
from app.testing.stub_vcs import register_stub_vcs

pytestmark = pytest.mark.service


def _vcs_pr(external_id: str, *, repo: str, number: int, title: str) -> VCSPullRequest:
    return VCSPullRequest(
        plugin_id="github",
        external_id=external_id,
        repo_external_id=repo,
        number=number,
        title=title,
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
        html_url=f"https://example.test/{external_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def _wait_for_inflight_to_drain() -> None:
    from app.domain.reviewer.queue import _inflight_tasks  # noqa: PLC0415

    if _inflight_tasks:
        await asyncio.gather(*list(_inflight_tasks.values()), return_exceptions=True)


@pytest.mark.asyncio
async def test_seeded_lesson_surfaces_in_prompt_sent_audit(db_session) -> None:
    org = await orgs_repo.insert_org(db_session, slug=f"svc-lesson-{uuid4().hex[:8]}")
    # Seed a lesson for the repo BEFORE the review runs.
    lesson = await memory.create(
        "owner/repo",
        "Cite the CWE family",
        "When flagging an input-validation issue, name the CWE family.",
        source_pr_url=None,
        actor=Actor.system(),
        org_id=org.id,
        plugin_id="github",
    )
    await db_session.commit()

    vcs_pr = _vcs_pr("owner/repo#31", repo="owner/repo", number=31, title="Add validation")

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
        await _wait_for_inflight_to_drain()

        review = (
            (await db_session.execute(select(ReviewRow).where(ReviewRow.org_id == org.id))).scalars().one()
        )
        assert review.status == "posted"

        prompt_sent_rows = (
            await db_session.execute(
                text(
                    "SELECT payload FROM audit_entries"
                    " WHERE entity_kind='review_job' AND entity_id=:id AND kind='review_job.prompt_sent'"
                ),
                {"id": review.id},
            )
        ).all()
        assert len(prompt_sent_rows) == 1
        payload = prompt_sent_rows[0][0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["lessons_count"] == 1
        assert str(lesson.id) in payload["lessons_applied"]
