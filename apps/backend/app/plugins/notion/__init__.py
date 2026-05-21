"""plugins/notion — Notion hosted-MCP IntegrationProvider."""

from app.plugins.notion.service import NotionProvider, bootstrap

__all__ = ["NotionProvider", "bootstrap"]

# Register at import time.
bootstrap()
