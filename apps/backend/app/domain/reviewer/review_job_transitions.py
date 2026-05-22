"""Write-side helpers for the legacy `review_jobs` row: status
transitions + per-step progress + the matching audit-payload Pydantic
shapes.

Extracted from `queue.py` so the legacy runner + `incremental.py` (which
also drives review-job state) can share them. Each function pairs a
`UPDATE review_jobs SET …` with an `audit_for_review_job(...)` write in
the same session so the audit row + row update are atomic.

The audit-payload Pydantic models (`Scheduled`, `Cancelled`, etc.) live
here too — they're the typed payload shape `audit_for_review_job`
serializes. None of them leak outside the legacy code path; once
queue.py + `incremental.py` are fully migrated they go away together.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import update

from app.core.audit_log import Actor, audit_for_review_job
from app.core.database import session as db_session
from app.core.events import publish
from app.domain.reviewer.models import ReviewRow
from app.domain.reviewer.queue_events import ReviewJobStepProgress

log = structlog.get_logger("reviewer.review_job_transitions")


# ── Audit payloads ────────────────────────────────────────────────────────


class ScheduledPayload(BaseModel):
    trigger_reason: str
    debounce_seconds: int


class CancelledPayload(BaseModel):
    reason: str


class PromptSentPayload(BaseModel):
    """Frozen snapshot of what influenced this review run."""

    prompt_hash: str
    lessons_count: int
    lessons_applied: list[UUID]
    checkout_sha: str
    language_hint: str | None = None


class PostedPayload(BaseModel):
    verdict: str
    finding_count: int
    findings_by_agent: dict[str, int]
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int
    review_external_id: str


class FailedPayload(BaseModel):
    invocation_status: str
    error: str | None
    raw_output_excerpt: str


class SkippedPayload(BaseModel):
    skip_reason: str


class AdmissionDropsPayload(BaseModel):
    """Audit payload for plan §10.5 admission drops (one row per review)."""

    drops: list[dict[str, Any]]


# ── Transitions ───────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def transition_failed(
    job_id: UUID,
    error: str,
    *,
    org_id: UUID,
    invocation_status: str = "agent_error",
    raw_output_excerpt: str = "",
    activity_log: list[dict[str, Any]] | None = None,
) -> None:
    """Flip the row to `failed`, stash the error, write a
    `review_job.failed` audit row. Same session, single commit."""
    values: dict[str, Any] = {
        "status": "failed",
        "completed_at": _utcnow(),
        "error_message": error,
        "current_step": "failed",
    }
    if activity_log is not None:
        values["activity_log"] = activity_log
    async with db_session() as s:
        await s.execute(update(ReviewRow).where(ReviewRow.id == job_id).values(**values))
        await audit_for_review_job(
            job_id,
            "review_job.failed",
            FailedPayload(
                invocation_status=invocation_status,
                error=error,
                raw_output_excerpt=raw_output_excerpt,
            ),
            actor=Actor.system(),
            org_id=org_id,
            session=s,
        )
        await s.commit()


async def transition_skipped(
    job_id: UUID,
    reason: str,
    *,
    org_id: UUID,
    activity_log: list[dict[str, Any]] | None = None,
) -> None:
    """Flip the row to `skipped` with the given reason; write a
    `review_job.skipped` audit row."""
    values: dict[str, Any] = {
        "status": "skipped",
        "skip_reason": reason,
        "completed_at": _utcnow(),
    }
    if activity_log is not None:
        values["activity_log"] = activity_log
    async with db_session() as s:
        await s.execute(update(ReviewRow).where(ReviewRow.id == job_id).values(**values))
        await audit_for_review_job(
            job_id,
            "review_job.skipped",
            SkippedPayload(skip_reason=reason),
            actor=Actor.system(),
            org_id=org_id,
            session=s,
        )
        await s.commit()


async def set_step(job_id: UUID, step: str, *, pr_id: UUID) -> None:
    """Update `current_step` + heartbeat; publish a `ReviewJobStepProgress`
    event so the SSE feed reflects the new step in near-real-time."""
    async with db_session() as s:
        await s.execute(
            update(ReviewRow)
            .where(ReviewRow.id == job_id)
            .values(current_step=step, last_heartbeat_at=_utcnow())
        )
        await s.commit()
    await publish(ReviewJobStepProgress(pr_id=pr_id, review_job_id=job_id, current_step=step))


__all__ = [
    "AdmissionDropsPayload",
    "CancelledPayload",
    "FailedPayload",
    "PostedPayload",
    "PromptSentPayload",
    "ScheduledPayload",
    "SkippedPayload",
    "set_step",
    "transition_failed",
    "transition_skipped",
]
