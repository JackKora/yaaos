"""Registry + dispatch for coding-agent plugins."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.workspace import Workspace
from app.domain.coding_agent.types import (
    CodingAgentPlugin,
    HealthStatus,
    PluginNotFoundError,
    ReviewContext,
    ReviewResult,
    ValidationResult,
)

log = structlog.get_logger("coding_agent")


_PLUGINS: dict[str, CodingAgentPlugin] = {}


def register_coding_agent_plugin(plugin: CodingAgentPlugin) -> None:
    if plugin.meta.id in _PLUGINS:
        raise ValueError(f"coding agent plugin {plugin.meta.id!r} already registered")
    _PLUGINS[plugin.meta.id] = plugin


def get_plugin(plugin_id: str) -> CodingAgentPlugin:
    try:
        return _PLUGINS[plugin_id]
    except KeyError as e:
        raise PluginNotFoundError(plugin_id) from e


def _reset_plugins_for_tests() -> None:
    _PLUGINS.clear()


async def review(plugin_id: str, workspace: Workspace, context: ReviewContext) -> ReviewResult:
    plugin = get_plugin(plugin_id)
    result = await plugin.review(workspace, context)
    log.info(
        "agent.reviewed",
        plugin_id=plugin_id,
        status=result.status,
        findings=len(result.findings),
        tokens_in=result.telemetry.tokens_in,
        tokens_out=result.telemetry.tokens_out,
        cost_usd=str(result.telemetry.cost_usd) if result.telemetry.cost_usd is not None else None,
        latency_ms=result.telemetry.latency_ms,
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
