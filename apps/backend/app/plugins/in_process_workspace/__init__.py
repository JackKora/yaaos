"""plugins/in_process_workspace — tempdir-based WorkspaceProvider for POC."""

from app.plugins.in_process_workspace.service import (
    InProcessWorkspaceProvider,
    bootstrap,
    get_provider,
)

__all__ = ["InProcessWorkspaceProvider", "bootstrap", "get_provider"]

# Registration runs at import time.
bootstrap()
