"""Worker process entrypoint.

Boots one event loop with:
  - the taskiq broker (Redis-backed) — consumes tasks from the queue
  - the outbox drain loop — pushes pending outbox rows into the broker

Both run as asyncio tasks via `asyncio.gather`. Single-process POC; the
two responsibilities split into separate compose services later if/when
scale demands it.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

import structlog
from taskiq.receiver import Receiver

from app.core import database, observability
from app.core import redis as redis_client
from app.core.tasks.broker import get_broker
from app.core.tasks.drain import drain_loop

log = structlog.get_logger("core.tasks.worker")


async def run() -> None:
    """Worker process body. Migrate the schema, import modules that carry
    `@task` decorators (registers them with the broker as a side-effect),
    then run drain + consumer side by side. Cancels both gracefully on
    SIGTERM/SIGINT.
    """
    observability.configure(role="worker")
    await database.migrate()

    broker = get_broker()
    # Import each module whose `@task` decorators register task bodies
    # with the broker. The decorator runs at import time and calls
    # `broker.task(...)` — no separate bind step needed.
    import app.core.workflow.service  # noqa: F401, PLC0415

    log.info("tasks.worker.booting", broker=type(broker).__name__)

    await broker.startup()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    drain_task = asyncio.create_task(drain_loop(broker), name="drain_loop")
    # `broker.listen()` is an async-generator yielding raw broker messages.
    # `Receiver` wraps it: consumes the generator, parses each message,
    # looks the registered @task body up by name, and dispatches.
    # `Receiver.listen(finish_event)` runs until the event is set; we
    # tie it to the same `stop` event the SIGTERM/SIGINT handler triggers.
    receiver = Receiver(broker, run_startup=False)
    consume_task = asyncio.create_task(receiver.listen(stop), name="broker_listen")
    stop_task = asyncio.create_task(stop.wait(), name="stop_signal")

    log.info("tasks.worker.running")
    done, pending = await asyncio.wait(
        {drain_task, consume_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    log.info(
        "tasks.worker.shutting_down",
        finished=[t.get_name() for t in done],
    )
    for t in pending:
        t.cancel()
    for t in pending:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    with contextlib.suppress(Exception):
        await broker.shutdown()
    with contextlib.suppress(Exception):
        await redis_client.aclose()
    await database.dispose()
    log.info("tasks.worker.stopped")
