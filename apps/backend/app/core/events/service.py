"""In-process pub/sub: domain modules publish typed events; SSE subscribers consume."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger("events")


class Event(BaseModel):
    """Base event envelope. Domain modules subclass with their own `kind` literal."""

    kind: str
    source_module: str
    ts: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    ticket_id: UUID | None = None


class EventFilter(BaseModel):
    ticket_id: UUID | None = None
    kinds: list[str] | None = None

    def matches(self, event: Event) -> bool:
        if self.ticket_id is not None and event.ticket_id != self.ticket_id:
            return False
        if self.kinds is not None and event.kind not in self.kinds:
            return False
        return True


# subscriber_id -> (filter, queue)
_subscribers: dict[str, tuple[EventFilter, asyncio.Queue[Event]]] = {}


async def publish(event: Event) -> None:
    """Dispatch to matching subscribers. Slow subscribers don't block fast ones —
    each has its own bounded queue; overflow drops with a log line."""
    for sub_id, (filt, queue) in list(_subscribers.items()):
        if filt.matches(event):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("event.dropped", subscriber=sub_id, kind=event.kind)


async def subscribe(filter: EventFilter) -> AsyncIterator[Event]:
    """Yield events matching `filter`. Unregisters on consumer exit."""
    sub_id = str(uuid4())
    queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)
    _subscribers[sub_id] = (filter, queue)
    try:
        while True:
            yield await queue.get()
    finally:
        _subscribers.pop(sub_id, None)


def _reset_for_tests() -> None:
    _subscribers.clear()


def subscriber_count() -> int:
    return len(_subscribers)


def serialize_for_sse(event: Event) -> str:
    """Serialize an Event for `text/event-stream` output."""
    return f"data: {event.model_dump_json()}\n\n"


# Helper for endpoint handler — keeps web.py simple and lets us reuse in tests.
async def stream_events_for_filter(filter: EventFilter) -> AsyncIterator[str]:
    async for event in subscribe(filter):
        yield serialize_for_sse(event)


# Re-export common typing alias for callers
EventDict = dict[str, Any]
