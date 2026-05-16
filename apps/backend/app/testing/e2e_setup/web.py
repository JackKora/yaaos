"""HTTP routes for the `e2e_setup` test surface.

Every route is gated on `yaaof_env == "dev"`. In prod the routes still mount
(because the testing tree is excluded from prod wheels, so prod never imports
this module — see `apps/backend/pyproject.toml`), but defense-in-depth here
ensures a stray dev-flagged build can't be probed for seed endpoints.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.webserver import RouteSpec, register_routes
from app.testing.e2e_setup import service

router = APIRouter()


def _guard_dev() -> None:
    if not service.is_dev_env():
        # 404 — pretend the route doesn't exist outside dev so prod scans
        # don't reveal the surface.
        raise HTTPException(status_code=404, detail="not found")


@router.post("/reset")
async def reset() -> dict[str, str]:
    _guard_dev()
    await service.reset()
    return {"status": "reset"}


class _CredentialsAndInstallRequest(BaseModel):
    org_login: str = Field(default="acme", min_length=1)


@router.post("/seed/credentials_and_install")
async def seed_credentials_and_install(
    req: _CredentialsAndInstallRequest | None = None,
) -> dict[str, str]:
    _guard_dev()
    payload = req or _CredentialsAndInstallRequest()
    await service.seed_credentials_and_install(org_login=payload.org_login)
    return {"status": "seeded"}


class _LessonRequest(BaseModel):
    repo_external_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)


@router.post("/seed/lesson")
async def seed_lesson(req: _LessonRequest) -> dict[str, str]:
    _guard_dev()
    lesson_id: UUID = await service.seed_lesson(
        repo_external_id=req.repo_external_id,
        title=req.title,
        body=req.body,
    )
    return {"status": "seeded", "lesson_id": str(lesson_id)}


register_routes(RouteSpec(module_name="e2e_setup", router=router, url_prefix="/api/testing"))
