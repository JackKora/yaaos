"""core/redis.shutdown — closes the client cache and drops the pub/sub
binding; registered on both web and worker shutdown registries."""

from __future__ import annotations

import pytest

import app.core.redis.service as _svc
from app.core.redis import bind_pubsub, shutdown
from app.core.redis.pubsub import RedisPubsub, _pubsub_var, get_pubsub
from app.core.redis.service import _get_client, _reset_clients_for_tests
from app.core.shutdown_registry import iter_web_shutdown_hooks, iter_worker_shutdown_hooks


@pytest.fixture(autouse=True)
async def _isolate():
    _reset_clients_for_tests()
    bind_pubsub(RedisPubsub())
    yield
    await _svc.shutdown()
    # Clear the ContextVar binding so the next test's pubsub_isolation
    # fixture starts from a clean slate (ContextVar is thread-local in the
    # test event loop).
    _pubsub_var.set(None)


@pytest.mark.asyncio
async def test_shutdown_clears_clients_and_drops_binding(redis_or_skip) -> None:
    """After shutdown() the client cache is empty and get_pubsub() raises."""
    _get_client()  # warm the cache
    get_pubsub()  # prove the binding exists before shutdown
    assert _svc._clients, "expected cache populated before shutdown"

    await shutdown()
    assert not _svc._clients
    # After shutdown, the ContextVar is set to None — get_pubsub should raise.
    assert _pubsub_var.get() is None


@pytest.mark.asyncio
async def test_shutdown_is_idempotent(redis_or_skip) -> None:
    """Calling shutdown() twice does not raise."""
    _get_client()
    await shutdown()
    await shutdown()  # must not raise


@pytest.mark.asyncio
async def test_shutdown_idempotent_without_state() -> None:
    """shutdown() on an empty cache + no binding is a no-op."""
    # Clear the binding installed by _isolate so we truly start empty.
    _pubsub_var.set(None)
    assert not _svc._clients
    await shutdown()  # must not raise


def test_shutdown_registered_on_both_registries() -> None:
    """core/redis registers shutdown() on the web and worker shutdown registries."""
    assert shutdown in iter_worker_shutdown_hooks()
    assert shutdown in iter_web_shutdown_hooks()


@pytest.mark.asyncio
async def test_worker_drain_drops_binding(redis_or_skip) -> None:
    """Draining the worker registry invokes shutdown, dropping the pub/sub binding."""
    get_pubsub()  # prove the binding exists
    assert _pubsub_var.get() is not None

    for hook in reversed(iter_worker_shutdown_hooks()):
        await hook()

    assert _pubsub_var.get() is None
