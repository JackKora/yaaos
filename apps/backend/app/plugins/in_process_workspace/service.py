"""In-process workspace provider — tempdir-backed, no real isolation. POC only."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.workspace import (
    HealthStatus,
    WorkspaceHandle,
    WorkspaceProvisionError,
    WorkspaceSpec,
    register_workspace_provider,
)

log = structlog.get_logger("in_process_workspace")


class InProcessWorkspaceProvider:
    plugin_id = "in_process"

    async def provision(self, spec: WorkspaceSpec) -> tuple[WorkspaceHandle, dict[str, Any]]:
        """Create a tempdir; write a tiny README marker. No git clone in M01 (the
        Claude Code CLI walks the dir itself; for our stub, this is sufficient)."""
        try:
            working_dir = tempfile.mkdtemp(prefix="yaaof-ws-")
            # Write a marker so downstream code can tell the dir is yaaof-managed.
            with open(os.path.join(working_dir, ".yaaof-workspace"), "w", encoding="utf-8") as f:
                f.write(f"plugin_id={spec.repo.plugin_id}\nrepo={spec.repo.external_id}\nsha={spec.sha}\n")
        except OSError as e:
            raise WorkspaceProvisionError(f"could not create tempdir: {e}") from e
        log.info(
            "workspace.in_process.provisioned",
            working_dir=working_dir,
            repo=spec.repo.external_id,
            sha=spec.sha,
        )
        return WorkspaceHandle(working_dir=working_dir), {"working_dir": working_dir}

    async def destroy(self, plugin_state: dict[str, Any]) -> None:
        working_dir = plugin_state.get("working_dir")
        if not working_dir:
            return
        if not os.path.isdir(working_dir):
            return
        # idempotent: ignore_errors handles concurrent cleanup
        shutil.rmtree(working_dir, ignore_errors=True)
        log.info("workspace.in_process.destroyed", working_dir=working_dir)

    async def health_check(self) -> HealthStatus:
        # tempdir is always available in M01.
        return HealthStatus(healthy=True, message="ok", checked_at=datetime.now(UTC))


_provider = InProcessWorkspaceProvider()


def bootstrap() -> None:
    """Register the provider. Called at import time from __init__."""
    register_workspace_provider(_provider)


def get_provider() -> InProcessWorkspaceProvider:
    return _provider
