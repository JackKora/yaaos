"""HTTP wiring for top-level org settings + M06 user-scoped/readiness endpoints.

| Method | Path                       | Action / auth                                       |
|--------|----------------------------|-----------------------------------------------------|
| GET    | `/api/orgs`                | `ORG_SETTINGS_READ` — top-level settings for the current org. |
| PATCH  | `/api/orgs`                | `ORG_SETTINGS_WRITE` — Owner/Admin update settings. |
| GET    | `/api/orgs/mine`           | session cookie only (cross-org) — M06 picker + switcher. |
| GET    | `/api/orgs/config-status`  | `ORG_READ` — M06 "not configured" gate aggregation. |

Org identified by `X-Org-Slug` header (M02 pattern). Architecture.md documents
the URL as `/api/orgs/{slug}` for readability; this implementation mirrors the
other M03 endpoints which all take the slug via header. The single endpoint
returns the updated org's relevant settings.

`workspace_provider` is `in_memory` or `remote_agent`. When set to
`remote_agent`, `registered_iam_arn` must also be set — the identity-exchange
verifier matches the agent's signed STS payload against this ARN.

`/api/orgs/mine` lives on the public allowlist (see `core/auth/types.py`)
because the SPA hits it before any org is selected — the session cookie
identifies the user; no `X-Org-Slug` header is involved. `last_used_at` is
null in M06 — there is no per-membership "last visited" column today
(Open Question 3 in `plan/milestones/M06-design-refresh/api-changes.md`).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.auth import public_route
from app.core.auth.context import org_id_var
from app.core.auth.types import Action
from app.core.database import session as db_session
from app.core.webserver import RouteSpec, register_routes
from app.domain.identity import repository as identity_repo
from app.domain.orgs import repository as orgs_repo
from app.domain.orgs.models import MembershipRow, OrgRow
from app.domain.orgs.onboarding import get_onboarding_status
from app.domain.sessions.dependencies import require

log = structlog.get_logger("orgs.settings.web")

router = APIRouter()


class _PatchOrgRequest(BaseModel):
    # Pydantic v2 allows the field to be absent OR explicitly null. Absent
    # = "don't touch"; null = "clear the override and fall back to the global
    # constant"; positive int = "set to N minutes".
    session_timeout_override: int | None = Field(default=None)
    _set_session_timeout_override: bool = False  # internal: did the client include the key?


_ALLOWED_WORKSPACE_PROVIDERS = {"in_memory", "remote_agent"}


class _OrgSettingsResponse(BaseModel):
    slug: str
    session_timeout_override: int | None
    workspace_provider: str | None = None
    registered_iam_arn: str | None = None


def _err(status: int, code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code})


@router.get("", dependencies=[Depends(require(Action.ORG_SETTINGS_READ))])
async def get_org_settings() -> _OrgSettingsResponse:
    """Return the current org's top-level settings. Lets the SPA's Settings
    page show what's actually set before the user edits."""
    org_id = org_id_var.get()
    if org_id is None:
        raise _err(400, "no_org_context")
    async with db_session() as s:
        row = (await s.execute(select(OrgRow).where(OrgRow.id == org_id))).scalar_one()
    return _OrgSettingsResponse(
        slug=row.slug,
        session_timeout_override=row.session_timeout_override,
        workspace_provider=row.workspace_provider,
        registered_iam_arn=row.registered_iam_arn,
    )


@router.patch("", dependencies=[Depends(require(Action.ORG_SETTINGS_WRITE))])
async def patch_org_settings(body: dict) -> _OrgSettingsResponse:
    """Update top-level org settings. Body is a JSON object; only the keys
    actually present are touched. M03 supports `session_timeout_override`
    (null clears it, positive int sets minutes)."""
    org_id = org_id_var.get()
    if org_id is None:
        raise _err(400, "no_org_context")

    async with db_session() as s:
        row = (await s.execute(select(OrgRow).where(OrgRow.id == org_id))).scalar_one()
        if "session_timeout_override" in body:
            value = body["session_timeout_override"]
            if value is not None:
                if not isinstance(value, int) or value <= 0:
                    raise _err(422, "invalid_session_timeout_override")
            row.session_timeout_override = value
        if "workspace_provider" in body:
            value = body["workspace_provider"]
            if value is not None and value not in _ALLOWED_WORKSPACE_PROVIDERS:
                raise _err(422, "invalid_workspace_provider")
            row.workspace_provider = value
        if "registered_iam_arn" in body:
            value = body["registered_iam_arn"]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise _err(422, "invalid_registered_iam_arn")
            row.registered_iam_arn = value
        # Cross-field: remote_agent provider requires an ARN.
        if row.workspace_provider == "remote_agent" and not row.registered_iam_arn:
            raise _err(422, "remote_agent_requires_iam_arn")
        await s.commit()
        await s.refresh(row)
    return _OrgSettingsResponse(
        slug=row.slug,
        session_timeout_override=row.session_timeout_override,
        workspace_provider=row.workspace_provider,
        registered_iam_arn=row.registered_iam_arn,
    )


class MineOrgView(BaseModel):
    id: UUID
    slug: str
    name: str
    role: str
    last_used_at: str | None


class ConfigStatusAdmin(BaseModel):
    user_id: UUID
    display_name: str
    primary_email: str | None


class ConfigStatusResponse(BaseModel):
    configured: bool
    missing: list[str]
    admins: list[ConfigStatusAdmin]


@router.get("/mine", dependencies=[Depends(public_route)])
async def list_mine(
    yaaos_session: Annotated[str | None, Cookie()] = None,
) -> JSONResponse:
    """Cross-org list of the user's memberships. Powers the org switcher and `/orgs` picker."""
    if not yaaos_session:
        return JSONResponse(status_code=401, content={"error": "unauthenticated"})
    token_hash = identity_repo.hash_token(yaaos_session)
    async with db_session() as s:
        row = await identity_repo.get_session_by_hash(s, token_hash)
        if row is None or row.user_id is None:
            return JSONResponse(status_code=401, content={"error": "unauthenticated"})
        from datetime import UTC, datetime  # noqa: PLC0415

        if row.expires_at < datetime.now(UTC):
            return JSONResponse(status_code=401, content={"error": "unauthenticated"})
        memberships = await orgs_repo.list_memberships_for_user(s, row.user_id)
        out: list[MineOrgView] = []
        for m in memberships:
            org = await orgs_repo.get_org(s, m.org_id)
            if org is None:
                continue
            out.append(
                MineOrgView(
                    id=org.id,
                    slug=org.slug,
                    name=org.display_name,
                    role=m.role,
                    last_used_at=None,
                )
            )
        out.sort(key=lambda o: o.slug)
    return JSONResponse(content=[o.model_dump(mode="json") for o in out])


@router.get("/config-status", dependencies=[Depends(require(Action.ORG_READ))])
async def config_status() -> ConfigStatusResponse:
    """Aggregated readiness for the M06 "not configured" gate."""
    org_id = org_id_var.get()
    if org_id is None:
        raise _err(400, "no_org_context")

    status = await get_onboarding_status(org_id=org_id)

    missing: list[str] = []
    if not status.github_app_installed:
        missing.append("vcs")
    if not status.anthropic_key_set:
        missing.append("api_key")
    # Coding-agent readiness piggybacks on the BYOK contributor today —
    # `anthropic_key_set` implies a Claude Code plugin row was provisioned at
    # the same point in the onboarding flow. When more coding-agent plugins
    # ship (Codex, Aider), this collapses into a separate contributor.

    async with db_session() as s:
        org_row = (await s.execute(select(OrgRow).where(OrgRow.id == org_id))).scalar_one()
        if not org_row.workspace_provider:
            missing.append("workspace_provider")

        admin_rows = (
            (
                await s.execute(
                    select(MembershipRow).where(
                        MembershipRow.org_id == org_id,
                        MembershipRow.role.in_(("owner", "admin")),
                    )
                )
            )
            .scalars()
            .all()
        )
        admins: list[ConfigStatusAdmin] = []
        for m in admin_rows:
            user = await identity_repo.get_user(s, m.user_id)
            if user is None:
                continue
            emails = await identity_repo.list_emails_for_user(s, m.user_id)
            primary = next(
                (e.email for e in emails if e.is_primary),
                emails[0].email if emails else None,
            )
            admins.append(
                ConfigStatusAdmin(
                    user_id=m.user_id,
                    display_name=user.display_name,
                    primary_email=primary,
                )
            )

    return ConfigStatusResponse(
        configured=not missing,
        missing=missing,
        admins=admins,
    )


register_routes(RouteSpec(module_name="orgs", router=router, url_prefix="/api/orgs"))
