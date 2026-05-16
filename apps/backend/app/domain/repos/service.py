"""Repo allowlist: CRUD + lookup."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import select, update

from app.core.audit_log import audit_for_repo
from app.core.database import session as db_session
from app.core.primitives import Actor
from app.domain.repos.models import RepoRow


class Repo(BaseModel):
    id: UUID
    org_id: UUID
    plugin_id: str
    external_id: str
    language_hint: str | None
    status: str
    added_at: datetime
    removed_at: datetime | None

    @classmethod
    def from_row(cls, row: RepoRow) -> Repo:
        return cls(
            id=row.id,
            org_id=row.org_id,
            plugin_id=row.plugin_id,
            external_id=row.external_id,
            language_hint=row.language_hint,
            status=row.status,
            added_at=row.added_at,
            removed_at=row.removed_at,
        )


class RepoNotFoundError(LookupError):
    pass


class _RepoAddedPayload(BaseModel):
    plugin_id: str
    external_id: str


class _RepoRemovedPayload(BaseModel):
    plugin_id: str
    external_id: str


class _LanguageDetectedPayload(BaseModel):
    language: str


async def add_repo(plugin_id: str, external_id: str, *, actor: Actor, org_id: UUID) -> Repo:
    """Add a repo to the allowlist. If a row exists in `removed` status,
    flip it back to active. Idempotent if already active."""
    async with db_session() as s:
        existing = (
            await s.execute(
                select(RepoRow).where(
                    RepoRow.org_id == org_id,
                    RepoRow.plugin_id == plugin_id,
                    RepoRow.external_id == external_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.status != "active":
                existing.status = "active"
                existing.removed_at = None
                await s.commit()
                await s.refresh(existing)
            row = existing
        else:
            row = RepoRow(
                id=uuid4(),
                org_id=org_id,
                plugin_id=plugin_id,
                external_id=external_id,
                status="active",
            )
            s.add(row)
            await s.commit()
            await s.refresh(row)

    await audit_for_repo(
        row.id,
        "repo.added",
        _RepoAddedPayload(plugin_id=plugin_id, external_id=external_id),
        actor=actor,
        org_id=org_id,
    )
    return Repo.from_row(row)


async def remove_repo(repo_id: UUID, *, actor: Actor, org_id: UUID) -> None:
    async with db_session() as s:
        await s.execute(
            update(RepoRow)
            .where(RepoRow.id == repo_id, RepoRow.org_id == org_id)
            .values(status="removed", removed_at=datetime.now(UTC))
        )
        await s.commit()
        row = (await s.execute(select(RepoRow).where(RepoRow.id == repo_id))).scalar_one_or_none()
    if row is not None:
        await audit_for_repo(
            row.id,
            "repo.removed",
            _RepoRemovedPayload(plugin_id=row.plugin_id, external_id=row.external_id),
            actor=actor,
            org_id=org_id,
        )


async def list_repos(*, org_id: UUID, include_removed: bool = False) -> list[Repo]:
    async with db_session() as s:
        stmt = select(RepoRow).where(RepoRow.org_id == org_id)
        if not include_removed:
            stmt = stmt.where(RepoRow.status == "active")
        stmt = stmt.order_by(RepoRow.added_at.desc())
        rows = (await s.execute(stmt)).scalars().all()
        return [Repo.from_row(r) for r in rows]


async def get(repo_id: UUID, *, org_id: UUID) -> Repo:
    async with db_session() as s:
        row = (
            await s.execute(select(RepoRow).where(RepoRow.id == repo_id, RepoRow.org_id == org_id))
        ).scalar_one_or_none()
    if row is None:
        raise RepoNotFoundError(str(repo_id))
    return Repo.from_row(row)


async def get_by_external(plugin_id: str, external_id: str, *, org_id: UUID) -> Repo | None:
    async with db_session() as s:
        row = (
            await s.execute(
                select(RepoRow).where(
                    RepoRow.org_id == org_id,
                    RepoRow.plugin_id == plugin_id,
                    RepoRow.external_id == external_id,
                )
            )
        ).scalar_one_or_none()
    return Repo.from_row(row) if row is not None else None


async def is_allowed(plugin_id: str, external_id: str, *, org_id: UUID) -> bool:
    repo = await get_by_external(plugin_id, external_id, org_id=org_id)
    return repo is not None and repo.status == "active"


async def set_language_hint(repo_id: UUID, language: str, *, actor: Actor, org_id: UUID) -> None:
    async with db_session() as s:
        await s.execute(
            update(RepoRow)
            .where(RepoRow.id == repo_id, RepoRow.org_id == org_id)
            .values(language_hint=language)
        )
        await s.commit()
    await audit_for_repo(
        repo_id,
        "repo.language_detected",
        _LanguageDetectedPayload(language=language),
        actor=actor,
        org_id=org_id,
    )


async def clear_language_hint(repo_id: UUID, *, org_id: UUID) -> None:
    async with db_session() as s:
        await s.execute(
            update(RepoRow).where(RepoRow.id == repo_id, RepoRow.org_id == org_id).values(language_hint=None)
        )
        await s.commit()
