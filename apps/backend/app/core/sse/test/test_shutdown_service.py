"""core/sse worker-shutdown hook — verifies shutdown() is registered on both
web and worker registries, and that the worker registry drain invokes it."""

from __future__ import annotations

import pytest

import app.core.sse  # noqa: F401 — triggers registration at import time
import app.core.sse.service as _svc
from app.core.shutdown_registry import (
    iter_web_shutdown_hooks,
    iter_worker_shutdown_hooks,
)
from app.core.sse.service import get_pubsub, shutdown


@pytest.fixture(autouse=True)
def _isolate():
    _svc._singleton = None
    yield
    _svc._singleton = None


@pytest.mark.asyncio
async def test_shutdown_registered_on_worker_registry() -> None:
    """core/sse registers shutdown() on the worker shutdown registry."""
    worker_hooks = iter_worker_shutdown_hooks()
    assert shutdown in worker_hooks, "core/sse.shutdown not found in worker shutdown registry"


@pytest.mark.asyncio
async def test_shutdown_registered_on_web_registry() -> None:
    """core/sse registers shutdown() on the web shutdown registry."""
    web_hooks = iter_web_shutdown_hooks()
    assert shutdown in web_hooks, "core/sse.shutdown not found in web shutdown registry"


@pytest.mark.asyncio
async def test_worker_drain_invokes_sse_shutdown() -> None:
    """Draining the worker registry calls core/sse shutdown, dropping the singleton."""
    get_pubsub()  # materialize singleton
    assert _svc._singleton is not None

    # Simulate worker process shutdown by calling each registered hook.
    for hook in reversed(iter_worker_shutdown_hooks()):
        await hook()

    assert _svc._singleton is None


@pytest.mark.service
@pytest.mark.asyncio
async def test_web_drain_invokes_sse_shutdown() -> None:
    """Draining the web registry calls core/sse shutdown, dropping the singleton."""
    get_pubsub()  # materialize singleton
    assert _svc._singleton is not None

    for hook in reversed(iter_web_shutdown_hooks()):
        await hook()

    assert _svc._singleton is None
