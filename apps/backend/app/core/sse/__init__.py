"""core/sse — Redis-backed pub/sub for ActivityEvent fanout.

Backed by Redis `PUBLISH`/`SUBSCRIBE` so a publish from the worker process
reaches an SSE subscriber attached to a different web process. Channel
name shape: `activity:{workflow_execution_id}`.
"""

from app.core.sse.service import (
    RedisPubsub,
    channel_for,
    get_pubsub,
    publish,
    reset_pubsub,
    shutdown,
    subscribe,
    subscriber_count,
)

__all__ = [
    "RedisPubsub",
    "channel_for",
    "get_pubsub",
    "publish",
    "reset_pubsub",
    "shutdown",
    "subscribe",
    "subscriber_count",
]

from app.core.shutdown_registry import (
    register_web_shutdown_hook,
    register_worker_shutdown_hook,
)

register_web_shutdown_hook(shutdown)
register_worker_shutdown_hook(shutdown)
