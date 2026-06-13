"""Test helpers for asserting OTel span state.

`span_capture()` installs an in-memory exporter on the global TracerProvider
for the duration of the `with` block, then yields the exporter so callers can
inspect finished spans. Use this in service tests that exercise FastAPI routes
or other instrumented code paths and want to assert on span names or attributes.

Usage::

    with span_capture() as exporter:
        # ... exercise instrumented code ...
        pass
    spans = exporter.get_finished_spans()
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

__all__ = ["span_capture"]


@contextmanager
def span_capture() -> Generator[InMemorySpanExporter]:
    """Context manager: install an in-memory span exporter, yield it, then remove it.

    Installs a `SimpleSpanProcessor` backed by an `InMemorySpanExporter` on the
    current global `TracerProvider`. Spans finished inside the `with` block are
    collected in the exporter. The processor is removed (shut down) on exit.

    Works regardless of whether `configure()` has been called — if the global
    provider is a no-op proxy the exporter sees no spans (also correct for tests
    that don't call `configure()`). The caller is responsible for ensuring
    `configure()` has been called if real spans are expected.
    """
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider = trace.get_tracer_provider()
    # The SDK TracerProvider exposes add_span_processor; no-op providers don't.
    # If the provider lacks the method (no-op), yield the empty exporter anyway.
    add = getattr(provider, "add_span_processor", None)
    if add is not None:
        add(processor)
    try:
        yield exporter
    finally:
        processor.shutdown()
