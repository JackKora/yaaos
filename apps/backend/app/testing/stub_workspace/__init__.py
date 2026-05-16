"""testing/stub_workspace — fake WorkspaceProvider for offline tests."""

from app.testing.stub_workspace.service import (
    StubWorkspaceProvider,
    wrap_all_registered_workspace_providers,
)

__all__ = ["StubWorkspaceProvider", "wrap_all_registered_workspace_providers"]
