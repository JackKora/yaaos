"""Read-side queries over the legacy `review_jobs` table.

Extracted from `queue.py` so the SPA endpoints in `reviewer/web.py` can
import the projections without depending on the legacy runner code.
The eventual queue.py file deletion + table drop happens in a later
slice; until then these queries are the canonical read API.

All four functions are pure SELECTs into `ReviewJob` Pydantic
projections — no event publishing, no side effects.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.database import session as db_session
from app.domain.reviewer.models import ReviewRow
from app.domain.reviewer.review_job import ReviewJob


async def get_review_job(review_job_id: UUID, *, org_id: UUID) -> ReviewJob:
    """Single review-job lookup scoped to `org_id`. Raises `LookupError`
    when the row doesn't exist (or belongs to a different org)."""
    async with db_session() as s:
        row = (
            await s.execute(
                select(ReviewRow).where(ReviewRow.id == review_job_id, ReviewRow.org_id == org_id)
            )
        ).scalar_one_or_none()
    if row is None:
        raise LookupError(str(review_job_id))
    return ReviewJob.from_row(row)


async def list_review_jobs_for_pr(pr_id: UUID, *, org_id: UUID) -> list[ReviewJob]:
    """All review jobs for one PR, newest first. Used by the per-PR
    history view in the SPA."""
    async with db_session() as s:
        rows = (
            (
                await s.execute(
                    select(ReviewRow)
                    .where(ReviewRow.pr_id == pr_id, ReviewRow.org_id == org_id)
                    .order_by(ReviewRow.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
    return [ReviewJob.from_row(r) for r in rows]


async def list_in_flight(*, org_id: UUID) -> list[ReviewJob]:
    """Org-scoped list of queued/running review jobs. Used by the org-
    dashboard "what's running" panel."""
    async with db_session() as s:
        rows = (
            (
                await s.execute(
                    select(ReviewRow).where(
                        ReviewRow.org_id == org_id,
                        ReviewRow.status.in_(["queued", "running"]),
                    )
                )
            )
            .scalars()
            .all()
        )
    return [ReviewJob.from_row(r) for r in rows]


async def metrics_summary(*, org_id: UUID) -> dict[str, Any]:
    """Aggregate counters for the basic-metrics requirement. Returns the
    counts-by-status dict plus posted/failed totals + a failure-rate
    fraction (0.0 when no posted+failed runs exist)."""
    async with db_session() as s:
        rows = (await s.execute(select(ReviewRow).where(ReviewRow.org_id == org_id))).scalars().all()
    statuses: dict[str, int] = {}
    posted = 0
    failed = 0
    for r in rows:
        statuses[r.status] = statuses.get(r.status, 0) + 1
        if r.status == "posted":
            posted += 1
        if r.status == "failed":
            failed += 1
    return {
        "review_jobs_by_status": statuses,
        "total_reviews_posted": posted,
        "failure_count": failed,
        "failure_rate": (failed / (posted + failed)) if (posted + failed) > 0 else 0.0,
    }


__all__ = [
    "get_review_job",
    "list_in_flight",
    "list_review_jobs_for_pr",
    "metrics_summary",
]
