"""HTTP routes for settings: onboarding status + plugin credential setters via registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.webserver import RouteSpec, register_routes
from app.domain.settings.service import OnboardingStatus, get_onboarding_status, health_summary

M01_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter()


CredentialSetter = Callable[[UUID, str], Awaitable[None]]
_CREDENTIAL_SETTERS: dict[str, CredentialSetter] = {}


def register_credential_setter(name: str, setter: CredentialSetter) -> None:
    """Plugins register their credential setters here (reverse-import avoided)."""
    _CREDENTIAL_SETTERS[name] = setter


def _reset_credential_setters_for_tests() -> None:
    _CREDENTIAL_SETTERS.clear()


class HealthSummaryResponse(BaseModel):
    onboarding: OnboardingStatus
    plugins: dict[str, dict[str, str | bool]]


class SetAnthropicKeyRequest(BaseModel):
    api_key: str


@router.get("/onboarding")
async def onboarding() -> OnboardingStatus:
    return await get_onboarding_status(org_id=M01_ORG_ID)


@router.get("/health")
async def health() -> HealthSummaryResponse:
    onboard = await get_onboarding_status(org_id=M01_ORG_ID)
    plugins = await health_summary()
    return HealthSummaryResponse(onboarding=onboard, plugins=plugins)


@router.post("/anthropic_key")
async def set_anthropic_key(req: SetAnthropicKeyRequest) -> dict[str, str]:
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail={"api_key": "must not be empty"})
    setter = _CREDENTIAL_SETTERS.get("anthropic_api_key")
    if setter is None:
        raise HTTPException(status_code=500, detail="claude_code plugin not registered")
    await setter(M01_ORG_ID, req.api_key)
    return {"status": "saved"}


register_routes(RouteSpec(module_name="settings", router=router))
