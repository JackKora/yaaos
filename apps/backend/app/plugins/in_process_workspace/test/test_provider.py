import os

import pytest

from app.core.workspace import RepoRefForSpec, WorkspaceSpec
from app.plugins.in_process_workspace import get_provider


@pytest.mark.asyncio
async def test_provision_then_destroy_cleans_tempdir() -> None:
    provider = get_provider()
    handle, state = await provider.provision(
        WorkspaceSpec(
            repo=RepoRefForSpec(plugin_id="github", external_id="acme/web"),
            sha="abc123",
        )
    )
    assert os.path.isdir(handle.working_dir)
    assert os.path.isfile(os.path.join(handle.working_dir, ".yaaof-workspace"))
    await provider.destroy(state)
    assert not os.path.isdir(handle.working_dir)


@pytest.mark.asyncio
async def test_destroy_is_idempotent() -> None:
    provider = get_provider()
    await provider.destroy({"working_dir": "/tmp/this-path-does-not-exist"})
    await provider.destroy({})  # missing key — no error


@pytest.mark.asyncio
async def test_health_check() -> None:
    h = await get_provider().health_check()
    assert h.healthy is True
