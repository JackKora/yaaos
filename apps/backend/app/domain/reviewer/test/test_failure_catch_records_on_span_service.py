"""Service test: failure-shaped catches in domain/reviewer record exception events on spans.

Samples the SecretsScan.context_fetch_failed path as a representative
failure catch: forces the workflow context provider to raise, then asserts
the surrounding span carries an `exception` event with ERROR status.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from app.testing.observability import span_capture

pytestmark = pytest.mark.service


class _RaisingProvider:
    """WorkflowContextProvider stub that always raises."""

    async def get_workspace_ticket_context(self, ticket_id: UUID):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated context fetch failure")


@pytest.mark.asyncio
async def test_reviewer_failure_catch_records_on_span() -> None:
    """SecretsScan.context_fetch_failed records exception event + ERROR on the active span."""
    from app.core.workspace import register_workflow_context_provider  # noqa: PLC0415
    from app.domain.reviewer.commands import SecretsScan  # noqa: PLC0415

    # Install the raising stub (isolation fixture resets to None after the test).
    register_workflow_context_provider(_RaisingProvider())

    cmd = SecretsScan()
    from app.core.workflow import CommandContext  # noqa: PLC0415

    ctx = CommandContext(
        ticket_id="00000000-0000-0000-0000-000000000001",
        workflow_execution_id="00000000-0000-0000-0000-000000000002",
        step_id="secrets_scan",
        attempt=0,
    )

    with span_capture() as exporter:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("workflow.command.SecretsScan"):
            outcome = await cmd.execute({}, ctx)

    assert outcome.kind.name == "FAILURE", f"expected FAILURE outcome, got {outcome.kind}"

    spans = exporter.get_finished_spans()
    target = next((s for s in spans if "SecretsScan" in s.name), None)
    assert target is not None, f"no SecretsScan span; got: {[s.name for s in spans]}"

    exception_events = [e for e in target.events if e.name == "exception"]
    assert exception_events, f"expected exception event on span, got: {[e.name for e in target.events]}"
    assert target.status.status_code == StatusCode.ERROR, (
        f"expected ERROR status, got {target.status.status_code}"
    )
