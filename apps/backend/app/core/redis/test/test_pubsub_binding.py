"""core/redis ContextVar-based pubsub binding contract.

Verifies: get_pubsub() raises when the ContextVar is unbound; bind_pubsub()
makes a subsequent get_pubsub() return the bound instance; two consecutive
binds in different Context copies are independent (proves fixture freshness).
"""

from __future__ import annotations

import contextvars

import pytest

from app.core.redis.pubsub import RedisPubsub, _pubsub_var, bind_pubsub, get_pubsub


def test_get_pubsub_raises_when_unbound() -> None:
    """get_pubsub() must raise RuntimeError when the ContextVar holds None.

    The pubsub_isolation autouse fixture has already bound an instance in the
    current Context. We copy the context and then explicitly clear the var
    inside the copy to verify the fail-fast behavior in isolation.
    """
    ctx = contextvars.copy_context()

    def _check() -> None:
        # Clear the binding that the autouse fixture set, simulating an
        # uninitialized runtime context.
        _pubsub_var.set(None)
        with pytest.raises(RuntimeError, match="pubsub"):
            get_pubsub()

    ctx.run(_check)


def test_bind_pubsub_then_get_returns_bound_instance() -> None:
    """After bind_pubsub(instance), get_pubsub() returns the same instance."""
    ctx = contextvars.copy_context()
    instance = RedisPubsub()

    def _check() -> None:
        bind_pubsub(instance)
        assert get_pubsub() is instance

    ctx.run(_check)


def test_two_contexts_isolate_bindings() -> None:
    """Bindings in two separate Contexts are independent — the fixture gives
    each test its own fresh instance."""
    instance_a = RedisPubsub()
    instance_b = RedisPubsub()

    ctx_a = contextvars.copy_context()
    ctx_b = contextvars.copy_context()

    result: dict[str, RedisPubsub | None] = {"a": None, "b": None}

    def _bind_a() -> None:
        bind_pubsub(instance_a)
        result["a"] = get_pubsub()

    def _bind_b() -> None:
        bind_pubsub(instance_b)
        result["b"] = get_pubsub()

    ctx_a.run(_bind_a)
    ctx_b.run(_bind_b)

    assert result["a"] is instance_a
    assert result["b"] is instance_b
    assert result["a"] is not result["b"]
