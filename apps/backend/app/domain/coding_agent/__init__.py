"""domain/coding_agent — Protocol + registry for coding-agent CLI plugins.

The Protocol exposes targeted methods (`review`, `reply`) — not a generic
`invoke(prompt, response_model)`. Plugins own prompt assembly + parsing;
consumers (today: `domain/reviewer`) hand over domain context and read
domain results.
"""

from app.domain.coding_agent.service import (
    _PLUGINS,
    _reset_plugins_for_tests,
    get_plugin,
    health_check_all,
    register_coding_agent_plugin,
    registered_plugin_ids,
    reply,
    review,
    validate_config,
)
from app.domain.coding_agent.types import (
    AgentSpec,
    CodingAgentCacheMiss,
    CodingAgentError,
    CodingAgentPlugin,
    HealthStatus,
    InvocationStatus,
    InvocationTelemetry,
    PluginNotFoundError,
    ReplyContext,
    ReplyResult,
    ReviewContext,
    ReviewResult,
    ValidationResult,
)

__all__ = [
    "_PLUGINS",
    "AgentSpec",
    "CodingAgentCacheMiss",
    "CodingAgentError",
    "CodingAgentPlugin",
    "HealthStatus",
    "InvocationStatus",
    "InvocationTelemetry",
    "PluginNotFoundError",
    "ReplyContext",
    "ReplyResult",
    "ReviewContext",
    "ReviewResult",
    "ValidationResult",
    "_reset_plugins_for_tests",
    "get_plugin",
    "health_check_all",
    "register_coding_agent_plugin",
    "registered_plugin_ids",
    "reply",
    "review",
    "validate_config",
]
