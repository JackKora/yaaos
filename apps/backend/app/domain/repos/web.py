"""HTTP routes for repo allowlist management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.primitives import Actor
from app.core.webserver import RouteSpec, register_routes
from app.domain.repos.service import (
    Repo,
    RepoNotFoundError,
    add_repo,
    clear_language_hint,
    get,
    list_repos,
    remove_repo,
)

# M01: single fixed org id.
M01_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter()


class AddRepoRequest(BaseModel):
    plugin_id: str = "github"
    external_id: str  # e.g., "acme/web"


@router.get("")
async def list_active() -> list[Repo]:
    return await list_repos(org_id=M01_ORG_ID)


@router.post("")
async def add(req: AddRepoRequest) -> Repo:
    if not req.external_id.strip():
        raise HTTPException(status_code=400, detail={"external_id": "must not be empty"})
    return await add_repo(req.plugin_id, req.external_id, actor=Actor.system(), org_id=M01_ORG_ID)


@router.delete("/{repo_id}")
async def remove(repo_id: UUID) -> dict[str, str]:
    try:
        await get(repo_id, org_id=M01_ORG_ID)
    except RepoNotFoundError:
        raise HTTPException(status_code=404, detail="repo not found")
    await remove_repo(repo_id, actor=Actor.system(), org_id=M01_ORG_ID)
    return {"status": "removed"}


@router.post("/{repo_id}/clear_language")
async def clear_lang(repo_id: UUID) -> dict[str, str]:
    await clear_language_hint(repo_id, org_id=M01_ORG_ID)
    return {"status": "cleared"}


register_routes(RouteSpec(module_name="repos", router=router))
