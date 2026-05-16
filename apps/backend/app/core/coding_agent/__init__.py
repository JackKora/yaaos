"""core/coding_agent — Protocol + registry for coding agent CLI plugins."""

from app.core.coding_agent.service import (
    _PLUGINS,
    _reset_plugins_for_tests,
    get_plugin,
    health_check_all,
    invoke,
    register_coding_agent_plugin,
    registered_plugin_ids,
    validate_config,
)
from app.core.coding_agent.types import (
    AgentInvocationResult,
    AgentInvocationStatus,
    AgentSpec,
    CodingAgentCacheMiss,
    CodingAgentError,
    CodingAgentPlugin,
    HealthStatus,
    PluginNotFoundError,
    ValidationResult,
)

__all__ = [
    "_PLUGINS",
    "AgentInvocationResult",
    "AgentInvocationStatus",
    "AgentSpec",
    "CodingAgentCacheMiss",
    "CodingAgentError",
    "CodingAgentPlugin",
    "HealthStatus",
    "PluginNotFoundError",
    "ValidationResult",
    "_reset_plugins_for_tests",
    "get_plugin",
    "health_check_all",
    "invoke",
    "register_coding_agent_plugin",
    "registered_plugin_ids",
    "validate_config",
]
