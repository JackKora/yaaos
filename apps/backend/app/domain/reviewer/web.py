"""HTTP routes for reviewer agents + review-job operations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.primitives import Actor
from app.core.webserver import RouteSpec, register_routes
from app.domain import tickets
from app.domain.reviewer.agent_crud import (
    AgentNotFoundError,
    ReviewerAgent,
    list_agents,
    reset_agent_prompt,
    update_agent_prompt,
)
from app.domain.reviewer.queue import (
    ReviewJob,
    list_review_jobs_for_pr,
    metrics_summary,
    schedule_review,
    startup_recovery,
)

M01_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter()


class UpdatePromptRequest(BaseModel):
    prompt_text: str


@router.get("/agents")
async def list_agents_route() -> list[ReviewerAgent]:
    return await list_agents(org_id=M01_ORG_ID)


@router.put("/agents/{name}/prompt")
async def set_prompt(name: str, req: UpdatePromptRequest) -> ReviewerAgent:
    if not req.prompt_text or not req.prompt_text.strip():
        raise HTTPException(status_code=400, detail={"prompt_text": "must not be empty"})
    try:
        return await update_agent_prompt(name, req.prompt_text, actor=Actor.system(), org_id=M01_ORG_ID)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="agent not found")


@router.post("/agents/{name}/reset_prompt")
async def reset_prompt(name: str) -> ReviewerAgent:
    try:
        return await reset_agent_prompt(name, actor=Actor.system(), org_id=M01_ORG_ID)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="agent not found")


class RereviewRequest(BaseModel):
    ticket_id: UUID


@router.post("/rereview")
async def rereview_ticket(req: RereviewRequest) -> dict[str, Any]:
    try:
        await tickets.get(req.ticket_id, org_id=M01_ORG_ID)
    except tickets.TicketNotFoundError:
        raise HTTPException(status_code=404, detail="ticket not found")
    ids = await schedule_review(
        ticket_id=req.ticket_id,
        agent_names="all",
        trigger_reason="ui_button",
        actor=Actor.system(),
        org_id=M01_ORG_ID,
    )
    return {"scheduled_count": len(ids), "review_job_ids": [str(i) for i in ids]}


@router.get("/jobs/by-ticket/{ticket_id}")
async def jobs_by_ticket(ticket_id: UUID) -> list[ReviewJob]:
    try:
        t = await tickets.get(ticket_id, org_id=M01_ORG_ID)
    except tickets.TicketNotFoundError:
        raise HTTPException(status_code=404, detail="ticket not found")
    if t.pr_id is None:
        return []
    return await list_review_jobs_for_pr(t.pr_id, org_id=M01_ORG_ID)


@router.get("/metrics")
async def metrics() -> dict[str, Any]:
    return await metrics_summary(org_id=M01_ORG_ID)


register_routes(RouteSpec(module_name="reviewer", router=router, on_startup=[startup_recovery]))
