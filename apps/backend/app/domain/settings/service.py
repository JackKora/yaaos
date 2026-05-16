"""Settings aggregator — answers 'is yaaof ready to operate?' via a contributor registry.

Plugins call `register_onboarding_contributor(name, check_fn)` at boot; this module
asks each contributor whether its readiness condition is met. Layering: plugins
depend on domain, never the reverse — so this registry pattern is the canonical
way for domain/settings to learn about plugin-owned readiness.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel

from app.core.coding_agent import health_check_all as cli_health_all
from app.core.workspace import health_check_all as workspace_health_all
from app.domain.repos import list_repos

OnboardingCheck = Callable[[UUID], Awaitable[bool]]

_CONTRIBUTORS: dict[str, OnboardingCheck] = {}


def register_onboarding_contributor(name: str, check: OnboardingCheck) -> None:
    """Register a named readiness check. Plugins call this at boot."""
    _CONTRIBUTORS[name] = check


def _reset_contributors_for_tests() -> None:
    _CONTRIBUTORS.clear()


class OnboardingStatus(BaseModel):
    github_app_installed: bool
    anthropic_key_set: bool
    at_least_one_repo: bool

    @property
    def all_ready(self) -> bool:
        return self.github_app_installed and self.anthropic_key_set and self.at_least_one_repo


async def get_onboarding_status(*, org_id: UUID) -> OnboardingStatus:
    """Ask each registered contributor whether its prereq is satisfied."""
    repos = await list_repos(org_id=org_id)
    gh = _CONTRIBUTORS.get("github_app_installed")
    cc = _CONTRIBUTORS.get("anthropic_key_set")
    return OnboardingStatus(
        github_app_installed=bool(gh) and await gh(org_id),
        anthropic_key_set=bool(cc) and await cc(org_id),
        at_least_one_repo=len(repos) > 0,
    )


async def health_summary() -> dict[str, dict[str, str | bool]]:
    """All plugin health, packaged for the dashboard endpoint."""
    coding = await cli_health_all()
    workspaces = await workspace_health_all()
    out: dict[str, dict[str, str | bool]] = {}
    for k, v in {**coding, **workspaces}.items():
        out[k] = {"healthy": v.healthy, "message": v.message}
    return out
