"""HTTP routes for the WorkspaceAgent wire protocol.

Five endpoints mounted under `/v1/`. The implementation calls into
`core.agent_gateway.service`; this module is the FastAPI shim. The
identity verifier in Phase 5 is a placeholder — it accepts any non-empty
bearer and trusts the `agent_pod_id` the caller supplies in
`/v1/identity/exchange`. The real STS-replay verifier lands in Phase 7.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Path
from fastapi.responses import JSONResponse, Response

from app.core.agent_gateway.service import (
    claim_next,
    record_agent_event,
    record_heartbeat,
    record_workspace_event,
)
from app.core.agent_gateway.types import (
    AgentEvent,
    ClaimRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    IdentityExchangeRequest,
    IdentityExchangeResponse,
    StaleClaimError,
    UnauthorizedError,
    WorkspaceEvent,
)
from app.core.auth.context import public_route
from app.core.database import session as db_session
from app.core.webserver import RouteSpec, register_routes

log = structlog.get_logger("agent_gateway.web")

router = APIRouter()


# ── Placeholder bearer verifier ─────────────────────────────────────────


def _verify_bearer(authorization: str | None) -> None:
    """Phase 5 placeholder. Phase 7 wires the real verifier that validates
    the bearer against the issuance log + checks expiry."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise UnauthorizedError("empty bearer")


def _bearer_dep(authorization: str | None = Header(default=None)) -> None:
    try:
        _verify_bearer(authorization)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "detail": str(exc)}) from exc


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post("/identity/exchange", dependencies=[Depends(public_route)])
async def exchange_identity(request: IdentityExchangeRequest) -> IdentityExchangeResponse:
    """Placeholder: accepts any non-empty `signed_request` and issues a
    24-hour bearer scoped to the supplied `agent_pod_id`. Phase 7 replaces
    the verification step with the real STS GetCallerIdentity replay."""
    if not request.signed_request:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "detail": "empty signed_request"},
        )
    # The agent_id is the per-pod row id in `workspace_agents`. Phase 5
    # synthesizes one per call; persistence comes with the wire-protocol
    # iteration that ships `workspace_agents` writes.
    return IdentityExchangeResponse(
        bearer=f"placeholder-{uuid4()}",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        agent_id=request.agent_pod_id,
    )


@router.post("/agents/{agent_id}/heartbeat", dependencies=[Depends(_bearer_dep)])
async def heartbeat(
    request: HeartbeatRequest,
    agent_id: UUID = Path(...),
) -> HeartbeatResponse:
    async with db_session() as s:
        response = await record_heartbeat(agent_id, request, session=s)
        await s.commit()
    return response


@router.post("/agents/{agent_id}/commands/claim", dependencies=[Depends(_bearer_dep)])
async def claim_command(
    request: ClaimRequest,
    agent_id: UUID = Path(...),
) -> Response:
    cmd = await claim_next(agent_id, wait_seconds=request.wait_seconds)
    if cmd is None:
        return Response(status_code=204)
    return JSONResponse(status_code=200, content=cmd.model_dump(mode="json"))


@router.post("/workspaces/{workspace_id}/events", dependencies=[Depends(_bearer_dep)])
async def post_workspace_event(
    event: WorkspaceEvent,
    workspace_id: UUID = Path(...),
) -> Response:
    if event.workspace_id != workspace_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "detail": "path and body workspace_id disagree"},
        )
    try:
        async with db_session() as s:
            await record_workspace_event(event, session=s)
            await s.commit()
    except StaleClaimError as exc:
        log.info("agent.workspace_event.stale", workspace_id=str(workspace_id), error=str(exc))
        return JSONResponse(status_code=410, content={"error": "stale_claim", "detail": str(exc)})
    return Response(status_code=200)


@router.post("/commands/{command_id}/events", dependencies=[Depends(_bearer_dep)])
async def post_command_event(
    event: AgentEvent,
    command_id: UUID = Path(...),
) -> Response:
    if event.command_id != command_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "detail": "path and body command_id disagree"},
        )
    try:
        async with db_session() as s:
            await record_agent_event(event, session=s)
            await s.commit()
    except StaleClaimError as exc:
        log.info("agent.command_event.stale", command_id=str(command_id), error=str(exc))
        return JSONResponse(status_code=410, content={"error": "stale_claim", "detail": str(exc)})
    return Response(status_code=200)


register_routes(RouteSpec(module_name="agent_gateway", router=router, url_prefix="/api/v1"))
