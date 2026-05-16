"""Plugin registry for VCSPlugin instances."""

from __future__ import annotations

from app.domain.vcs.types import PluginNotFoundError, VCSPlugin

_PLUGINS: dict[str, VCSPlugin] = {}


def register_vcs_plugin(plugin: VCSPlugin) -> None:
    if plugin.plugin_id in _PLUGINS:
        raise ValueError(f"VCS plugin {plugin.plugin_id!r} already registered")
    _PLUGINS[plugin.plugin_id] = plugin


def get_plugin(plugin_id: str) -> VCSPlugin:
    try:
        return _PLUGINS[plugin_id]
    except KeyError as e:
        raise PluginNotFoundError(plugin_id) from e


def is_registered(plugin_id: str) -> bool:
    return plugin_id in _PLUGINS


def registered_plugin_ids() -> list[str]:
    return list(_PLUGINS.keys())


def _reset_for_tests() -> None:
    _PLUGINS.clear()
