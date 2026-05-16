"""plugins/claude_code — Claude Code CLI wrapper for core/coding_agent."""

from app.plugins.claude_code.models import ClaudeCodeSettingsRow
from app.plugins.claude_code.service import ClaudeCodePlugin, bootstrap, get_plugin

__all__ = ["ClaudeCodePlugin", "ClaudeCodeSettingsRow", "bootstrap", "get_plugin"]

# Register at import time.
bootstrap()
