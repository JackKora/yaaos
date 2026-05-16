"""Registry + dispatch for coding agent plugins."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel

from app.core.coding_agent.types import (
    AgentInvocationResult,
    CodingAgentPlugin,
    HealthStatus,
    PluginNotFoundError,
    ValidationResult,
)
from app.core.workspace import Workspace

log = structlog.get_logger("coding_agent")


_PLUGINS: dict[str, CodingAgentPlugin] = {}


def register_coding_agent_plugin(plugin: CodingAgentPlugin) -> None:
    if plugin.plugin_id in _PLUGINS:
        raise ValueError(f"coding agent plugin {plugin.plugin_id!r} already registered")
    _PLUGINS[plugin.plugin_id] = plugin


def get_plugin(plugin_id: str) -> CodingAgentPlugin:
    try:
        return _PLUGINS[plugin_id]
    except KeyError as e:
        raise PluginNotFoundError(plugin_id) from e


def _reset_plugins_for_tests() -> None:
    _PLUGINS.clear()


async def invoke(
    plugin_id: str,
    workspace: Workspace,
    prompt: str,
    agent_config: dict[str, Any],
    response_model: type[BaseModel],
) -> AgentInvocationResult[Any]:
    plugin = get_plugin(plugin_id)
    result = await plugin.invoke(workspace, prompt, agent_config, response_model)
    log.info(
        "agent.invoked",
        plugin_id=plugin_id,
        status=result.status,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=str(result.cost_usd) if result.cost_usd is not None else None,
        latency_ms=result.latency_ms,
    )
    return result


async def validate_config(plugin_id: str, agent_config: dict[str, Any]) -> ValidationResult:
    return await get_plugin(plugin_id).validate_config(agent_config)


async def health_check_all() -> dict[str, HealthStatus]:
    out: dict[str, HealthStatus] = {}
    for plugin_id, plugin in _PLUGINS.items():
        try:
            out[plugin_id] = await plugin.health_check()
        except Exception as e:
            out[plugin_id] = HealthStatus(healthy=False, message=str(e), checked_at=datetime.now(UTC))
    return out


def registered_plugin_ids() -> list[str]:
    return list(_PLUGINS.keys())
