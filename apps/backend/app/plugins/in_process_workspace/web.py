"""HTTP routes owned by the in_process_workspace plugin.

Plugin-owned URL namespace per `plan/milestones/M01-code-review/backend.md` §
2026-05-16 — each plugin exposes its health check under `/api/<plugin>/...`.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.webserver import RouteSpec, register_routes
from app.plugins.in_process_workspace.service import get_provider

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, object]:
    h = await get_provider().health_check()
    return {"healthy": h.healthy, "message": h.message, "checked_at": h.checked_at}


register_routes(RouteSpec(module_name="in_process", router=router))
