"""Isolation fixtures for service tests.

Provides pytest fixtures that reset per-module singletons to a clean state
before each test. All resets are performed by calling each module's production
registration/deregistration APIs — no direct submodule attribute access.
"""

from __future__ import annotations

import pytest_asyncio

from app.core.redis import RedisPubsub, bind_pubsub


@pytest_asyncio.fixture(autouse=True)
async def pubsub_isolation() -> None:
    """Bind a fresh RedisPubsub instance for each test.

    Autouse so every test in the backend suite gets an isolated pubsub
    without importing or calling anything. Tests that depend on Redis
    still use the `redis_or_skip` fixture to gate on reachability.
    """
    bind_pubsub(RedisPubsub())
