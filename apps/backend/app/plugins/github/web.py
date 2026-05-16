"""HTTP webhook receiver for GitHub events."""

from __future__ import annotations

import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.database import session as db_session
from app.core.webserver import RouteSpec, register_routes
from app.plugins.github.models import GitHubAppInstallationRow, GitHubSettingsRow
from app.plugins.github.payload_parser import parse_webhook
from app.plugins.github.service import (
    mark_webhook_processed,
    record_webhook_event,
    verify_webhook_signature,
)

log = structlog.get_logger("github.webhook")

M01_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter()


@router.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
) -> JSONResponse:
    body = await request.body()

    # Look up the webhook secret to verify the signature
    async with db_session() as s:
        settings_row = (await s.execute(select(GitHubSettingsRow).limit(1))).scalar_one_or_none()
    if settings_row is None:
        log.warning("github.webhook.no_settings_row")
        return JSONResponse(status_code=400, content={"error": "github_settings missing"})

    from cryptography.fernet import Fernet  # noqa: PLC0415

    from app.core.config import get_settings  # noqa: PLC0415

    fernet = Fernet(get_settings().yaaof_encryption_key.encode())
    secret = fernet.decrypt(settings_row.encrypted_webhook_secret)
    if not verify_webhook_signature(body, x_hub_signature_256, secret):
        log.warning("github.webhook.bad_signature", delivery=x_github_delivery)
        return JSONResponse(status_code=400, content={"error": "bad signature"})

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "bad json"})

    # Resolve org_id from installation if present.
    install_id = (payload.get("installation") or {}).get("id")
    org_id = settings_row.org_id
    if install_id is not None:
        async with db_session() as s:
            install = (
                await s.execute(
                    select(GitHubAppInstallationRow).where(
                        GitHubAppInstallationRow.install_external_id == str(install_id)
                    )
                )
            ).scalar_one_or_none()
        if install is not None:
            org_id = install.org_id

    row_id = await record_webhook_event(
        x_github_delivery or f"event-{id(payload)}",
        x_github_event,
        payload,
        org_id=org_id,
    )
    if row_id is None:
        # Already seen — idempotent success.
        return JSONResponse(status_code=200, content={"status": "duplicate"})

    events = parse_webhook(x_github_event, x_github_delivery or str(row_id), payload)

    # Dispatch into intake (lazy import to avoid layering issues).
    if events:
        from app.domain.intake import handle_vcs_events  # noqa: PLC0415

        try:
            await handle_vcs_events(events, org_id=org_id)
        except Exception:
            log.exception("github.webhook.dispatch_failed", delivery=x_github_delivery)

    await mark_webhook_processed(row_id)
    return JSONResponse(status_code=200, content={"status": "ok"})


register_routes(RouteSpec(module_name="github", router=router))
