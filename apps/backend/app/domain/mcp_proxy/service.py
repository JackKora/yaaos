"""Per-review MCP bearer lifecycle.

`mint_token(review_id) -> raw_token` issues a fresh bearer for a review:
32 URL-safe random bytes returned to the caller once, sha256-hashed and
persisted with `expires_at = created_at + 2h`. `lookup_token(raw)` reverses
the dance — returns the row if not expired, None otherwise. `revoke_token`
deletes by review_id (reviewer calls it at review-end). `sweep_expired`
drops anything past TTL (called once a day by the scheduler).

Raw tokens never persist. Lookups are constant-time-safe because the hash
is the primary key.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session as db_session
from app.domain.mcp_proxy.models import McpReviewTokenRow

log = structlog.get_logger("domain.mcp_proxy")


REVIEW_TOKEN_TTL = timedelta(hours=2)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def mint_token(
    review_id: UUID,
    *,
    session: AsyncSession | None = None,
) -> str:
    """Issue a fresh bearer for a review. Returns the raw token exactly once;
    the DB sees only the sha256 hash."""
    raw = secrets.token_urlsafe(32)
    row = McpReviewTokenRow(
        token_hash=_hash(raw),
        review_id=review_id,
        expires_at=datetime.now(UTC) + REVIEW_TOKEN_TTL,
    )

    async def _write(s: AsyncSession) -> None:
        s.add(row)
        await s.flush()

    if session is not None:
        await _write(session)
    else:
        async with db_session() as s:
            await _write(s)
            await s.commit()
    return raw


async def lookup_token(
    raw_token: str,
    *,
    session: AsyncSession | None = None,
) -> McpReviewTokenRow | None:
    """Return the row matching `raw_token` if not expired; None otherwise.
    Raw tokens never live in the DB — we hash and look up by primary key."""
    token_hash = _hash(raw_token)

    async def _read(s: AsyncSession) -> McpReviewTokenRow | None:
        row = (
            await s.execute(select(McpReviewTokenRow).where(McpReviewTokenRow.token_hash == token_hash))
        ).scalar_one_or_none()
        if row is None:
            return None
        if row.expires_at < datetime.now(UTC):
            return None
        return row

    if session is not None:
        return await _read(session)
    async with db_session() as s:
        return await _read(s)


async def revoke_token(
    review_id: UUID,
    *,
    session: AsyncSession | None = None,
) -> int:
    """Drop every token row for a review. Returns the count removed (review
    teardown calls this before the workspace is destroyed)."""

    async def _delete(s: AsyncSession) -> int:
        result = await s.execute(delete(McpReviewTokenRow).where(McpReviewTokenRow.review_id == review_id))
        return int(result.rowcount or 0)

    if session is not None:
        return await _delete(session)
    async with db_session() as s:
        n = await _delete(s)
        await s.commit()
        return n


async def sweep_expired(*, session: AsyncSession | None = None) -> int:
    """Periodic-cleanup helper. Drops rows past TTL; returns the count."""

    async def _sweep(s: AsyncSession) -> int:
        result = await s.execute(
            delete(McpReviewTokenRow).where(McpReviewTokenRow.expires_at < datetime.now(UTC))
        )
        return int(result.rowcount or 0)

    if session is not None:
        return await _sweep(session)
    async with db_session() as s:
        n = await _sweep(s)
        await s.commit()
        return n
