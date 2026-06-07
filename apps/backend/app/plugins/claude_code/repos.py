"""Repo-row service for the claude_code plugin.

Owns the `claude_code_repos` table. Provides `get_or_create_repo_row` —
an upsert for the per-(org, repo) identity row.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select

from app.plugins.claude_code.models import ClaudeCodeRepoRow

if True:
    from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger("claude_code.repos")


async def get_or_create_repo_row(
    org_id: UUID,
    repo_external_id: str,
    *,
    session: AsyncSession,
) -> ClaudeCodeRepoRow:
    """Return the existing row or create a new one. Never commits."""
    row = (
        await session.execute(
            select(ClaudeCodeRepoRow).where(
                ClaudeCodeRepoRow.org_id == org_id,
                ClaudeCodeRepoRow.repo_external_id == repo_external_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ClaudeCodeRepoRow(
            org_id=org_id,
            repo_external_id=repo_external_id,
        )
        session.add(row)
        await session.flush()
    return row
