"""`refresh_pr_metadata` is idempotent for the same `(org, source, ext_id)` slot.

Migration 025 added a UNIQUE constraint on `(org_id, source, source_external_id)`;
the intake path uses `INSERT ... ON CONFLICT DO NOTHING` so two webhook deliveries
for the same PR — sequential here, concurrent in production — collapse to a single
ticket row, a single `ticket.created` audit row, and a single `TicketStatusChanged`
publication.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.audit_log.models import AuditEntryRow
from app.domain.identity import repository as identity_repo
from app.domain.intake.service import refresh_pr_metadata
from app.domain.orgs import repository as orgs_repo
from app.domain.tickets.models import TicketRow
from app.domain.vcs.types import VCSPullRequest


def _pr() -> VCSPullRequest:
    return VCSPullRequest(
        plugin_id="github",
        external_id="JackKora/umami#3",
        repo_external_id="JackKora/umami",
        number=3,
        title="Add /api/links/lookup endpoint",
        body="Body text.",
        author_login="JackKora",
        author_type="user",
        base_branch="main",
        head_branch="feat/lookup",
        base_sha="a" * 40,
        head_sha="b" * 40,
        is_draft=False,
        is_fork=False,
        state="open",
        html_url="https://github.com/JackKora/umami/pull/3",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.service
@pytest.mark.asyncio
async def test_concurrent_refresh_collapses_to_single_ticket(db_session) -> None:  # type: ignore[no-untyped-def]
    user = await identity_repo.insert_user(db_session, display_name="J")
    org = await orgs_repo.insert_org(db_session, slug="race-org")
    await db_session.commit()
    del user

    pr = _pr()
    first = await refresh_pr_metadata("JackKora/umami", pr, org_id=org.id)
    second = await refresh_pr_metadata("JackKora/umami", pr, org_id=org.id)

    # Both callers get the same PR row back.
    assert first.id == second.id

    # Exactly one ticket row for this (org, source, external_id).
    n_tickets = (
        await db_session.execute(
            select(func.count())
            .select_from(TicketRow)
            .where(
                TicketRow.org_id == org.id,
                TicketRow.source == "github_pr",
                TicketRow.source_external_id == pr.external_id,
            )
        )
    ).scalar_one()
    assert n_tickets == 1

    # The PR points at that one ticket.
    ticket = (
        await db_session.execute(
            select(TicketRow).where(
                TicketRow.org_id == org.id,
                TicketRow.source_external_id == pr.external_id,
            )
        )
    ).scalar_one()
    assert ticket.pr_id == first.id

    # Exactly one `ticket.created` audit row (the loser must not emit one).
    n_created = (
        await db_session.execute(
            select(func.count())
            .select_from(AuditEntryRow)
            .where(
                AuditEntryRow.entity_kind == "ticket",
                AuditEntryRow.entity_id == ticket.id,
                AuditEntryRow.kind == "ticket.created",
            )
        )
    ).scalar_one()
    assert n_created == 1
