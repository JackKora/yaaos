"""HTTP wiring for `core/sse`.

| Method | Path                  | Auth                |
|--------|-----------------------|---------------------|
| GET    | `/api/sse/general`    | `ORG_READ` — org-scoped general event stream for the caller's resolved org. |

The `/api/sse` prefix is classified as `ORG_SCOPED` in `core/auth/types.py`,
so `AuthMiddleware` enforces the `X-Org-Slug` header before the handler runs.
`require(Action.ORG_READ)` resolves the session → membership → sets
`org_id_var` and marks the route security resolved.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import Action, org_id_var
from app.core.sessions import require
from app.core.sse.service import serialize_for_sse, subscribe_general
from app.core.webserver import RouteSpec, register_routes

router = APIRouter()


async def _general_stream(org_id) -> AsyncIterator[str]:
    """Translate general pub/sub events into SSE frames for the caller's org."""
    async for event in subscribe_general(org_id):
        yield serialize_for_sse(event)


@router.get("/general", dependencies=[Depends(require(Action.ORG_READ))])
async def stream_general() -> StreamingResponse:
    """Subscribe an SSE client to the general org-scoped event stream.

    Returns `text/event-stream`; closes when the client disconnects. Each
    frame is `data: <json>\\n\\n` carrying a `GeneralEventKind`-typed payload.
    Only events published to the caller's resolved org reach this stream —
    cross-org isolation is enforced by the per-org Redis channel shape.
    """
    org_id = org_id_var.get()
    return StreamingResponse(_general_stream(org_id), media_type="text/event-stream")


register_routes(RouteSpec(module_name="sse", router=router, url_prefix="/api/sse"))
