"""Redis-backed pub/sub for ActivityEvent fanout.

Publishers call `publish(channel, event)` with `channel =
activity:{workflow_execution_id}`; subscribers iterate `async for event in
subscribe(channel)`. Backed by Redis `PUBLISH` / `SUBSCRIBE` so a publish
from the worker process reaches an SSE subscriber attached to a different
web process. Fire-and-forget per Redis semantics — slow consumers do not
backpressure publishers.

Channel naming convention: `activity:{workflow_execution_id}`. The caller
is responsible for forming the key via `channel_for()`. The SSE handler in
`web.py` subscribes per workflow execution; `core/agent_gateway` (and the
reviewer's direct activity publisher) publish.

The Pydantic-encoded payload crosses the seam as a `dict[str, Any]`
serialized to JSON on Redis; the channel name discriminates routing. No
per-event ack; activity is fire-and-forget per architecture.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

import structlog
from redis.asyncio import from_url

from app.core.config import get_settings

log = structlog.get_logger("core.sse_pubsub")


class RedisPubsub:
    """Redis pub/sub wrapper that matches the in-process API the rest of
    the app depends on.

    `subscriber_count` is **local-process** — Redis's `PUBSUB NUMSUB`
    returns the cluster-wide count, which is the right answer for "is
    anyone listening anywhere?" but not for the demand-pull diagnostics
    callers want. The local count is enough for tests asserting register/
    unregister bookkeeping.

    Client construction is lazy so importing the module (or constructing
    the singleton) doesn't require a live Redis — useful for tests that
    don't touch SSE.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._local_counts: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        self._local_counts.clear()

    async def publish(self, channel: str, event: dict[str, Any]) -> int:
        """Publish to `channel`. Returns the number of clients Redis
        delivered to cluster-wide. Returns 0 when nobody is listening.

        Creates a fresh client per call: redis-py's async client binds
        its connection pool to the event loop where the first call ran,
        so cross-loop reuse (web handler in one loop, drain in another,
        tests via TestClient's portal loop) breaks. POC-acceptable cost;
        swap to a per-loop pool if publish QPS becomes a hot path.
        """
        client = from_url(self._url, decode_responses=True)
        try:
            payload = json.dumps(event)
            n = await client.publish(channel, payload)
            return int(n)
        finally:
            with contextlib.suppress(Exception):
                await client.aclose()

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Async iterator over events on `channel`. Registers a Redis
        subscription on first iteration; unregisters on iterator close
        (consumer cancellation, exhaustion, or context exit).

        Filters out Redis's own subscribe/unsubscribe confirmation
        messages — callers only see `message` payloads. Creates a fresh
        client per iterator so the connection pool stays bound to the
        consumer's loop.
        """
        client = from_url(self._url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        async with self._lock:
            self._local_counts[channel] = self._local_counts.get(channel, 0) + 1
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                data = msg.get("data")
                if not isinstance(data, str):
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    log.warning("sse_pubsub.malformed_payload", channel=channel)
                    continue
        finally:
            async with self._lock:
                cur = self._local_counts.get(channel, 0)
                if cur <= 1:
                    self._local_counts.pop(channel, None)
                else:
                    self._local_counts[channel] = cur - 1
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(channel)
            with contextlib.suppress(Exception):
                await pubsub.aclose()
            with contextlib.suppress(Exception):
                await client.aclose()

    def subscriber_count(self, channel: str) -> int:
        """Local-process subscriber count for diagnostics / tests."""
        return self._local_counts.get(channel, 0)


_singleton: RedisPubsub | None = None


def get_pubsub() -> RedisPubsub:
    """Process-singleton pub/sub. Constructed lazily from
    `settings.redis_url` — required at boot, see [core/config](
    core_config.md).
    """
    global _singleton
    if _singleton is None:
        _singleton = RedisPubsub(get_settings().redis_url)
    return _singleton


def _reset_for_tests() -> None:
    """Drop the singleton. Tests call this in setup/teardown to keep
    state from leaking between cases. Per-call/per-iterator Redis
    clients are owned by their callers, so resetting the singleton has
    no lingering connections to clean up.
    """
    global _singleton
    _singleton = None


async def publish(channel: str, event: dict[str, Any]) -> int:
    """Module-level convenience: publish to the process singleton."""
    return await get_pubsub().publish(channel, event)


def subscribe(channel: str) -> AsyncIterator[dict[str, Any]]:
    """Module-level convenience: subscribe via the process singleton.

    Returns an async iterator, not a coroutine — consumers do
    `async for event in subscribe(...)`.
    """
    return get_pubsub().subscribe(channel)


def channel_for(workflow_execution_id: str) -> str:
    """Channel key used by publishers and SSE subscribers. Centralized so
    the naming convention stays consistent across both sides of the
    fanout.
    """
    return f"activity:{workflow_execution_id}"


def subscriber_count(channel: str) -> int:
    return get_pubsub().subscriber_count(channel)
