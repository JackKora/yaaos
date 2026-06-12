"""Service tests: `_safe_execute` records span status on raises and failure outcomes.

Three tests covering the child `workflow.command.{kind}` span emitted by
`_safe_execute`, and outer `workflow.start_step` span propagation:

- `test_safe_execute_records_exception_on_raise` — a command that raises →
  child span is `StatusCode.ERROR` with an `exception` event; outer
  `workflow.start_step` span is also `StatusCode.ERROR`.

- `test_safe_execute_sets_error_status_on_failure_outcome` — a command that
  returns `Outcome.failure(reason="...")` → both spans are `StatusCode.ERROR`;
  no `exception` event (none was raised).

- `test_safe_execute_ok_on_success_outcome` — regression guard; a command
  that returns `Outcome.success()` leaves both spans unset (not ERROR).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from opentelemetry.trace import StatusCode

from app.core.tasks import drain_once, get_pending_task_names
from app.core.workflow import (
    CommandCategory,
    Outcome,
    Step,
    TerminalAction,
    Workflow,
    WorkflowState,
)
from app.core.workflow.models import WorkflowExecutionRow
from app.testing.observability import span_capture
from app.testing.workflow_harness import scoped_engine

pytestmark = pytest.mark.service


# ── Minimal test commands ──────────────────────────────────────────────


class _RaisingLocal:
    """Raises RuntimeError from execute() — _safe_execute must record it."""

    kind = "RaisingLocalCmd"
    category = CommandCategory.LOCAL
    restart_safe = True

    async def execute(self, inputs, ctx):  # type: ignore[no-untyped-def]
        del inputs, ctx
        raise RuntimeError("boom")


class _FailingLocal:
    """Returns Outcome.failure() — _safe_execute must mark the span ERROR."""

    kind = "FailingLocalCmd"
    category = CommandCategory.LOCAL
    restart_safe = True

    async def execute(self, inputs, ctx):  # type: ignore[no-untyped-def]
        del inputs, ctx
        return Outcome.failure(reason="planned-failure")


class _SucceedingLocal:
    """Returns Outcome.success() — spans must remain unset (not ERROR)."""

    kind = "SucceedingLocalCmd"
    category = CommandCategory.LOCAL
    restart_safe = True

    async def execute(self, inputs, ctx):  # type: ignore[no-untyped-def]
        del inputs, ctx
        return Outcome.success()


# ── Drain helper ───────────────────────────────────────────────────────


async def _drain(db_session) -> None:  # type: ignore[no-untyped-def]
    """Drive outbox rows through task bodies until empty."""
    from app.core.tasks import get_broker  # noqa: PLC0415

    async def _dispatcher(kind: str, payload: dict) -> None:
        assert kind == "taskiq_enqueue"
        decorated = get_broker().find_task(payload["task_name"])
        assert decorated is not None, f"no task body for {payload['task_name']}"
        await decorated.original_func(**payload["args"])

    for _ in range(50):
        pending = await get_pending_task_names(db_session)
        if not pending:
            return
        delivered = await drain_once(db_session, dispatcher=_dispatcher)
        await db_session.commit()
        if delivered == 0:
            return


# ── Tests ──────────────────────────────────────────────────────────────


async def test_safe_execute_records_exception_on_raise(db_session) -> None:
    """A command that raises → child `workflow.command.RaisingLocalCmd` span is
    `StatusCode.ERROR` with an `exception` event; the outer
    `workflow.start_step` span is also `StatusCode.ERROR`."""
    cmd = _RaisingLocal()
    wf = Workflow(
        name="span-raise-test",
        version=1,
        steps=(
            Step(
                id="step",
                command_kind="RaisingLocalCmd",
                transitions={"failure": TerminalAction.FAIL_WORKFLOW},
            ),
        ),
        entry_step_id="step",
    )

    with span_capture() as exporter:
        with scoped_engine() as eng:
            eng.register_command(cmd)
            eng.register_workflow(wf)
            wfx_id = await eng.start(
                workflow_name="span-raise-test",
                ticket_id=str(uuid4()),
                session=db_session,
            )
            await db_session.commit()
            await _drain(db_session)

    wfx = await db_session.get(WorkflowExecutionRow, wfx_id)
    assert wfx.state == WorkflowState.FAILED.value, f"expected FAILED, got {wfx.state}"

    spans = exporter.get_finished_spans()
    span_names = [s.name for s in spans]

    # Child span: workflow.command.RaisingLocalCmd
    child_spans = [s for s in spans if s.name == "workflow.command.RaisingLocalCmd"]
    assert child_spans, f"expected workflow.command.RaisingLocalCmd span, got {span_names}"
    child = child_spans[0]
    assert child.status.status_code == StatusCode.ERROR, (
        f"child span status expected ERROR, got {child.status.status_code}"
    )
    exception_events = [e for e in child.events if e.name == "exception"]
    assert exception_events, "expected an 'exception' event on the child span"

    # Outer span: workflow.start_step also ERROR
    outer_spans = [s for s in spans if s.name == "workflow.start_step"]
    assert outer_spans, f"expected workflow.start_step span, got {span_names}"
    outer = outer_spans[0]
    assert outer.status.status_code == StatusCode.ERROR, (
        f"outer start_step span expected ERROR, got {outer.status.status_code}"
    )


async def test_safe_execute_sets_error_status_on_failure_outcome(db_session) -> None:
    """A command returning `Outcome.failure(reason=...)` → both
    `workflow.command.FailingLocalCmd` and `workflow.start_step` are
    `StatusCode.ERROR` with the reason as description; NO `exception` event."""
    cmd = _FailingLocal()
    wf = Workflow(
        name="span-failure-test",
        version=1,
        steps=(
            Step(
                id="step",
                command_kind="FailingLocalCmd",
                transitions={"failure": TerminalAction.FAIL_WORKFLOW},
            ),
        ),
        entry_step_id="step",
    )

    with span_capture() as exporter:
        with scoped_engine() as eng:
            eng.register_command(cmd)
            eng.register_workflow(wf)
            wfx_id = await eng.start(
                workflow_name="span-failure-test",
                ticket_id=str(uuid4()),
                session=db_session,
            )
            await db_session.commit()
            await _drain(db_session)

    wfx = await db_session.get(WorkflowExecutionRow, wfx_id)
    assert wfx.state == WorkflowState.FAILED.value, f"expected FAILED, got {wfx.state}"

    spans = exporter.get_finished_spans()
    span_names = [s.name for s in spans]

    # Child span
    child_spans = [s for s in spans if s.name == "workflow.command.FailingLocalCmd"]
    assert child_spans, f"expected workflow.command.FailingLocalCmd span, got {span_names}"
    child = child_spans[0]
    assert child.status.status_code == StatusCode.ERROR, (
        f"child span expected ERROR, got {child.status.status_code}"
    )
    assert "planned-failure" in (child.status.description or ""), (
        f"expected failure reason in status description, got {child.status.description!r}"
    )
    # No exception event — command returned a failure outcome, it did not raise.
    exception_events = [e for e in child.events if e.name == "exception"]
    assert not exception_events, f"unexpected exception event on child span: {exception_events}"

    # Outer span
    outer_spans = [s for s in spans if s.name == "workflow.start_step"]
    assert outer_spans, f"expected workflow.start_step span, got {span_names}"
    outer = outer_spans[0]
    assert outer.status.status_code == StatusCode.ERROR, (
        f"outer start_step span expected ERROR, got {outer.status.status_code}"
    )
    assert "planned-failure" in (outer.status.description or ""), (
        f"expected failure reason in outer status description, got {outer.status.description!r}"
    )


async def test_safe_execute_ok_on_success_outcome(db_session) -> None:
    """Regression guard: a success outcome leaves both spans with default
    status (not ERROR). Neither span should have an `exception` event."""
    cmd = _SucceedingLocal()
    wf = Workflow(
        name="span-success-test",
        version=1,
        steps=(
            Step(
                id="step",
                command_kind="SucceedingLocalCmd",
                transitions={"success": TerminalAction.COMPLETE_WORKFLOW},
            ),
        ),
        entry_step_id="step",
    )

    with span_capture() as exporter:
        with scoped_engine() as eng:
            eng.register_command(cmd)
            eng.register_workflow(wf)
            wfx_id = await eng.start(
                workflow_name="span-success-test",
                ticket_id=str(uuid4()),
                session=db_session,
            )
            await db_session.commit()
            await _drain(db_session)

    wfx = await db_session.get(WorkflowExecutionRow, wfx_id)
    assert wfx.state == WorkflowState.DONE.value, f"expected DONE, got {wfx.state}"

    spans = exporter.get_finished_spans()

    # Child span: no ERROR status
    child_spans = [s for s in spans if s.name == "workflow.command.SucceedingLocalCmd"]
    assert child_spans, "expected workflow.command.SucceedingLocalCmd span"
    child = child_spans[0]
    assert child.status.status_code != StatusCode.ERROR, (
        f"child span must not be ERROR on success, got {child.status.status_code}"
    )
    exception_events = [e for e in child.events if e.name == "exception"]
    assert not exception_events, f"unexpected exception event: {exception_events}"

    # Outer span: no ERROR status
    outer_spans = [s for s in spans if s.name == "workflow.start_step"]
    assert outer_spans, "expected workflow.start_step span"
    outer = outer_spans[0]
    assert outer.status.status_code != StatusCode.ERROR, (
        f"outer span must not be ERROR on success, got {outer.status.status_code}"
    )
