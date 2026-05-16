"""Agent CRUD service — owns reviewer_agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import select

from app.core.audit_log import audit_for_reviewer_agent
from app.core.database import session as db_session
from app.core.primitives import Actor
from app.domain.reviewer.models import ReviewerAgentRow
from app.domain.reviewer.seeds import DEFAULT_PROMPTS, builtin_prompt


class ReviewerAgent(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    prompt_text: str
    coding_agent_plugin_id: str
    agent_config: dict[str, Any]
    is_built_in: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: ReviewerAgentRow) -> ReviewerAgent:
        return cls(
            id=row.id,
            org_id=row.org_id,
            name=row.name,
            prompt_text=row.prompt_text,
            coding_agent_plugin_id=row.coding_agent_plugin_id,
            agent_config=row.agent_config,
            is_built_in=row.is_built_in,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class AgentNotFoundError(LookupError):
    pass


class _PromptUpdatedPayload(BaseModel):
    prior_hash: str
    new_hash: str
    restored_to_default: bool = False


def _hash(s: str) -> str:
    import hashlib  # noqa: PLC0415

    return hashlib.sha256(s.encode()).hexdigest()[:16]


async def list_agents(*, org_id: UUID) -> list[ReviewerAgent]:
    async with db_session() as s:
        rows = (
            (
                await s.execute(
                    select(ReviewerAgentRow)
                    .where(ReviewerAgentRow.org_id == org_id)
                    .order_by(ReviewerAgentRow.name.asc())
                )
            )
            .scalars()
            .all()
        )
    return [ReviewerAgent.from_row(r) for r in rows]


async def get_agent_by_name(name: str, *, org_id: UUID) -> ReviewerAgent:
    async with db_session() as s:
        row = (
            await s.execute(
                select(ReviewerAgentRow).where(
                    ReviewerAgentRow.org_id == org_id, ReviewerAgentRow.name == name
                )
            )
        ).scalar_one_or_none()
    if row is None:
        raise AgentNotFoundError(name)
    return ReviewerAgent.from_row(row)


async def get_agent_by_id(agent_id: UUID, *, org_id: UUID) -> ReviewerAgent:
    async with db_session() as s:
        row = (
            await s.execute(
                select(ReviewerAgentRow).where(
                    ReviewerAgentRow.org_id == org_id, ReviewerAgentRow.id == agent_id
                )
            )
        ).scalar_one_or_none()
    if row is None:
        raise AgentNotFoundError(str(agent_id))
    return ReviewerAgent.from_row(row)


def validate_prompt_text(prompt_text: str) -> None:
    if not prompt_text or not prompt_text.strip():
        raise ValueError("prompt_text must not be empty")


async def update_agent_prompt(
    name: str, new_prompt_text: str, *, actor: Actor, org_id: UUID
) -> ReviewerAgent:
    validate_prompt_text(new_prompt_text)
    async with db_session() as s:
        row = (
            await s.execute(
                select(ReviewerAgentRow).where(
                    ReviewerAgentRow.org_id == org_id, ReviewerAgentRow.name == name
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise AgentNotFoundError(name)
        prior_hash = _hash(row.prompt_text)
        row.prompt_text = new_prompt_text
        await s.commit()
        await s.refresh(row)
        row_id = row.id

    await audit_for_reviewer_agent(
        row_id,
        "reviewer_agent.prompt_updated",
        _PromptUpdatedPayload(prior_hash=prior_hash, new_hash=_hash(new_prompt_text)),
        actor=actor,
        org_id=org_id,
    )
    return await get_agent_by_name(name, org_id=org_id)


async def reset_agent_prompt(name: str, *, actor: Actor, org_id: UUID) -> ReviewerAgent:
    default = builtin_prompt(name)
    async with db_session() as s:
        row = (
            await s.execute(
                select(ReviewerAgentRow).where(
                    ReviewerAgentRow.org_id == org_id, ReviewerAgentRow.name == name
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise AgentNotFoundError(name)
        prior_hash = _hash(row.prompt_text)
        row.prompt_text = default
        await s.commit()
        await s.refresh(row)
        row_id = row.id

    await audit_for_reviewer_agent(
        row_id,
        "reviewer_agent.prompt_updated",
        _PromptUpdatedPayload(prior_hash=prior_hash, new_hash=_hash(default), restored_to_default=True),
        actor=actor,
        org_id=org_id,
    )
    return await get_agent_by_name(name, org_id=org_id)


async def ensure_builtin_agents(*, org_id: UUID) -> list[ReviewerAgent]:
    """Idempotent — insert any missing built-in rows."""
    async with db_session() as s:
        existing_names = {
            row.name
            for row in (await s.execute(select(ReviewerAgentRow).where(ReviewerAgentRow.org_id == org_id)))
            .scalars()
            .all()
        }
        for name, prompt in DEFAULT_PROMPTS.items():
            if name in existing_names:
                continue
            s.add(
                ReviewerAgentRow(
                    id=uuid4(),
                    org_id=org_id,
                    name=name,
                    prompt_text=prompt,
                    coding_agent_plugin_id="claude_code",
                    agent_config={},
                    is_built_in=True,
                )
            )
        await s.commit()
    return await list_agents(org_id=org_id)
