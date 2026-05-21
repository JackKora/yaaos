"""domain/integrations — per-(org, provider) hosted-MCP OAuth credentials.

Phase 1: service surface (connect_callback / get / clear / validate /
update_allowlist). Advisory-lock-guarded `refresh` ships in a later sub-phase.
"""

from app.domain.integrations.models import McpCredentialRow
from app.domain.integrations.service import (
    clear,
    connect_callback,
    get,
    update_allowlist,
    validate,
)
from app.domain.integrations.types import (
    BrokenCredentialsError,
    IntegrationError,
    IntegrationNotConnectedError,
    IntegrationProvider,
    ProviderConfig,
    ProviderNotRegisteredError,
    get_provider,
    known_providers,
    register_provider,
)

__all__ = [
    "BrokenCredentialsError",
    "IntegrationError",
    "IntegrationNotConnectedError",
    "IntegrationProvider",
    "McpCredentialRow",
    "ProviderConfig",
    "ProviderNotRegisteredError",
    "clear",
    "connect_callback",
    "get",
    "get_provider",
    "known_providers",
    "register_provider",
    "update_allowlist",
    "validate",
]
