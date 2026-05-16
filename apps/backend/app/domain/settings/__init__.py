"""domain/settings — onboarding status aggregator + plugin-contributor registries."""

from app.domain.settings import web  # noqa: F401 — registers HTTP routes
from app.domain.settings.service import (
    OnboardingStatus,
    get_onboarding_status,
    health_summary,
    register_onboarding_contributor,
)
from app.domain.settings.web import register_credential_setter

__all__ = [
    "OnboardingStatus",
    "get_onboarding_status",
    "health_summary",
    "register_credential_setter",
    "register_onboarding_contributor",
]
