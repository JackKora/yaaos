"""HTTP routes for `/api/account/*` — user-scoped (not org-scoped).

| Method | Path | Action |
|---|---|---|
| GET    | `/api/account/emails`             | `ACCOUNT_UPDATE_SELF` — list the cookie-bearer's emails. |
| POST   | `/api/account/emails`             | `ACCOUNT_UPDATE_SELF` — add an unverified email (verification flow ships later). |
| DELETE | `/api/account/emails/{email_id}`  | `ACCOUNT_UPDATE_SELF` — remove an email; blocked when it's the last verified one. |

These routes are user-scoped — the `X-Org-Slug` header is required by the
middleware (since `/api/account/` is in `M02_PROTECTED_PREFIXES`) but only
used to assert membership-in-something. Actions still operate on the user.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth.context import user_id_var
from app.core.auth.types import Action
from app.core.database import session as db_session
from app.core.webserver import RouteSpec, register_routes

log = structlog.get_logger("identity.account.web")

router = APIRouter()


class _AddEmailRequest(BaseModel):
    email: str


class EmailView(BaseModel):
    id: UUID
    email: str
    is_primary: bool
    verified: bool


def _err(status: int, code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code})


def _require_account():
    """Lazy: domain/auth imports domain/identity, so the dep factory has
    to be looked up at call time, not at module import."""
    from app.domain.auth.dependencies import require  # noqa: PLC0415

    return require(Action.ACCOUNT_UPDATE_SELF)


@router.get("/emails", dependencies=[Depends(_require_account())])
async def list_emails() -> list[EmailView]:
    from app.domain.identity import repository as identity_repo  # noqa: PLC0415

    user_id = user_id_var.get()
    if user_id is None:
        raise _err(401, "unauthenticated")
    async with db_session() as s:
        rows = await identity_repo.list_emails_for_user(s, user_id)
    return [
        EmailView(id=r.id, email=r.email, is_primary=r.is_primary, verified=r.verified_at is not None)
        for r in rows
    ]


@router.post("/emails", dependencies=[Depends(_require_account())])
async def add_email(
    body: _AddEmailRequest,
    yaaos_csrf: Annotated[str | None, Cookie()] = None,
) -> EmailView:
    from app.domain.identity import repository as identity_repo  # noqa: PLC0415

    user_id = user_id_var.get()
    if user_id is None:
        raise _err(401, "unauthenticated")
    async with db_session() as s:
        row = await identity_repo.add_email(
            s, user_id=user_id, email=body.email.lower(), is_primary=False, verified=False
        )
        await s.commit()
    return EmailView(id=row.id, email=row.email, is_primary=row.is_primary, verified=False)


@router.delete("/emails/{email_id}", dependencies=[Depends(_require_account())])
async def remove_email(email_id: UUID) -> dict[str, str]:
    from sqlalchemy import select  # noqa: PLC0415

    from app.domain.identity import repository as identity_repo  # noqa: PLC0415
    from app.domain.identity.models import UserEmailRow  # noqa: PLC0415

    user_id = user_id_var.get()
    if user_id is None:
        raise _err(401, "unauthenticated")
    async with db_session() as s:
        row = (
            await s.execute(
                select(UserEmailRow).where(UserEmailRow.id == email_id, UserEmailRow.user_id == user_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise _err(404, "email_not_found")
        # Last-verified-email invariant.
        if row.verified_at is not None:
            verified_count = await identity_repo.count_verified_emails(s, user_id)
            if verified_count <= 1:
                raise _err(409, "last_verified_email")
        deleted = await identity_repo.delete_email(s, user_id=user_id, email_id=email_id)
        if not deleted:
            raise _err(404, "email_not_found")
        await s.commit()
    return {"ok": "deleted"}


register_routes(RouteSpec(module_name="account", router=router, url_prefix="/api/account"))


__all__ = ["router"]
