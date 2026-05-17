"""SQLAlchemy models for review_jobs + posted_comments.

One row per (PR x review run). No per-agent decomposition — a single parent
reviewer dispatches subagents internally; the row records the whole run.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReviewJobRow(Base):
    __tablename__ = "review_jobs"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    pr_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    # Why this review was scheduled. Values: `pr_ready`, `pr_synchronized`,
    # `rereview_command`, `ui_rereview`. Future: `implementer_loop` once an
    # implementer module exists to call `run_review`.
    triggered_by: Mapped[str] = mapped_column(String, nullable=False, server_default="pr_ready")
    # Where the review result went. `vcs` (today: posted via the VCS plugin).
    # Future: `caller` when `run_review` returns findings without posting.
    destination: Mapped[str] = mapped_column(String, nullable=False, server_default="vcs")
    skip_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_step: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    lessons_applied: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), nullable=True
    )
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    review_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Each finding object carries a `source_agent` field naming which subagent
    # surfaced it (e.g. "yaaos-architecture").
    findings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_review_jobs_pr_status_created", "pr_id", "status", "created_at"),
        Index("ix_review_jobs_status_heartbeat", "status", "last_heartbeat_at"),
    )


class PostedCommentRow(Base):
    __tablename__ = "posted_comments"

    external_comment_id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    pr_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=False
    )
    review_job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("review_jobs.id"), nullable=False
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
