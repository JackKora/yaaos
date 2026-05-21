"""HTTP wiring for cross-cutting system-readiness aggregation.

Preserves the legacy M01 endpoints at `/api/settings/onboarding` and
`/api/settings/plugins`. The aggregator logic + onboarding-contributor
registry live alongside the rest of `domain/orgs` (see `onboarding.py`);
this file is just the route surface.

`/plugins` walks the three plugin registries directly — no service-layer
helper — so the domain stays free of stale aggregators. The M03 picker
endpoint at `/api/plugins/available?type=...` is the future of this surface;
this endpoint remains for the legacy M01 plugin-health card.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import public_route
from app.core.plugin_meta import PluginMeta
from app.core.webserver import RouteSpec, register_routes
from app.core.workspace.service import _PROVIDERS as _WORKSPACE_PROVIDERS
from app.domain.coding_agent.service import _PLUGINS as _CODING_AGENT_PLUGINS
from app.domain.orgs.onboarding import OnboardingStatus, get_onboarding_status
from app.domain.vcs.registry import _PLUGINS as _VCS_PLUGINS

M01_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

router = APIRouter(dependencies=[Depends(public_route)])


@router.get("/onboarding")
async def onboarding() -> OnboardingStatus:
    return await get_onboarding_status(org_id=M01_ORG_ID)


@router.get("/plugins")
def plugins() -> list[PluginMeta]:
    """Every registered plugin's metadata. Walks the three registries in a
    stable order (VCS → coding-agent → workspace) — UI rows render
    consistently across reloads."""
    out: list[PluginMeta] = []
    for plugin in _VCS_PLUGINS.values():
        out.append(plugin.meta)
    for plugin in _CODING_AGENT_PLUGINS.values():
        out.append(plugin.meta)
    for provider in _WORKSPACE_PROVIDERS.values():
        out.append(provider.meta)
    return out


register_routes(RouteSpec(module_name="onboarding", router=router, url_prefix="/api/settings"))
