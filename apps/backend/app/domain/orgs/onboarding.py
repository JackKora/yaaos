"""Onboarding status aggregator + onboarding-contributor registry.

`get_onboarding_status(org_id)` asks each registered contributor ("is your
prereq satisfied for this org?") and returns one `OnboardingStatus`. Plugins
(`plugins/github`, `plugins/claude_code`) register at bootstrap. Lives in
`domain/orgs` because the readiness state is per-org and the dashboard uses
it as a per-org readiness signal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel

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

    @property
    def all_ready(self) -> bool:
        return self.github_app_installed and self.anthropic_key_set


async def get_onboarding_status(*, org_id: UUID) -> OnboardingStatus:
    """Ask each registered contributor whether its prereq is satisfied."""
    gh = _CONTRIBUTORS.get("github_app_installed")
    cc = _CONTRIBUTORS.get("anthropic_key_set")
    return OnboardingStatus(
        github_app_installed=bool(gh) and await gh(org_id),
        anthropic_key_set=bool(cc) and await cc(org_id),
    )


__all__ = [
    "OnboardingCheck",
    "OnboardingStatus",
    "get_onboarding_status",
    "register_onboarding_contributor",
]
