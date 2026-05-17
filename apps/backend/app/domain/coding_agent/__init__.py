"""domain/coding_agent — Protocol + registry for coding-agent CLI plugins.

The Protocol exposes `review(context)`. Plugins own prompt assembly + parsing;
consumers (today: `domain/reviewer`) hand over domain context and read domain
results. Subagent definitions live under `app/domain/coding_agent/reviewers/`
and are installed into the local Claude Code agent directory by the
`plugins/claude_code` plugin at bootstrap.
"""

from app.domain.coding_agent.service import (
    _PLUGINS,
    _reset_plugins_for_tests,
    get_plugin,
    health_check_all,
    register_coding_agent_plugin,
    registered_plugin_ids,
    review,
    validate_config,
)
from app.domain.coding_agent.types import (
    CodingAgentCacheMiss,
    CodingAgentError,
    CodingAgentPlugin,
    HealthStatus,
    InvocationStatus,
    InvocationTelemetry,
    PluginNotFoundError,
    ReviewContext,
    ReviewResult,
    ValidationResult,
)

__all__ = [
    "_PLUGINS",
    "CodingAgentCacheMiss",
    "CodingAgentError",
    "CodingAgentPlugin",
    "HealthStatus",
    "InvocationStatus",
    "InvocationTelemetry",
    "PluginNotFoundError",
    "ReviewContext",
    "ReviewResult",
    "ValidationResult",
    "_reset_plugins_for_tests",
    "get_plugin",
    "health_check_all",
    "register_coding_agent_plugin",
    "registered_plugin_ids",
    "review",
    "validate_config",
]
