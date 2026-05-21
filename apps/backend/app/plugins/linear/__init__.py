"""plugins/linear — Linear hosted-MCP IntegrationProvider."""

from app.plugins.linear.service import LinearProvider, bootstrap

__all__ = ["LinearProvider", "bootstrap"]

# Register at import time.
bootstrap()
