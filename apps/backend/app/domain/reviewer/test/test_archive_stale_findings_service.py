"""`ArchiveStaleFindings` — covers the defensive branches that don't need a
real reviewer aggregate fixture. Happy-path (finding actually transitions
to STALE) is exercised via `domain/reviewer/test/test_aggregate.py`'s
state-machine coverage; the wrapper logic here is what we verify.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.workflow import CommandContext
from app.core.workspace import (
    WorkspaceTicketContext,
    register_workflow_context_provider,
)
from app.domain.reviewer.commands import ArchiveStaleFindings


def _ctx() -> CommandContext:
    return CommandContext(
        workflow_execution_id=str(uuid4()),
        ticket_id=str(uuid4()),
        step_id="archive",
        attempt=0,
    )


class _StaticProvider:
    def __init__(self, context: WorkspaceTicketContext | None) -> None:
        self._context = context

    async def get_workspace_ticket_context(self, ticket_id):  # type: ignore[no-untyped-def]
        del ticket_id
        return self._context


async def test_empty_input_returns_success_zero_archived(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """No finding_ids in inputs → nothing to do, success-no-op. Returns
    before reaching the provider call."""
    register_workflow_context_provider(_StaticProvider(context=None))
    outcome = await ArchiveStaleFindings().execute({}, _ctx())
    assert outcome.label == "success"
    assert outcome.outputs.get("archived_count") == 0


async def test_ticket_not_found_is_noop_success(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """Provider returns None → success with archived_count=0. Workflow
    cleanup-after-failure shouldn't re-fail."""
    register_workflow_context_provider(_StaticProvider(context=None))
    outcome = await ArchiveStaleFindings().execute({"stale_finding_ids": [str(uuid4())]}, _ctx())
    assert outcome.label == "success"
    assert outcome.outputs.get("archived_count") == 0


async def test_no_pr_id_is_noop_success(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """Ticket exists but isn't linked to a PR row yet → success-no-op."""
    register_workflow_context_provider(
        _StaticProvider(
            context=WorkspaceTicketContext(
                org_id=uuid4(),
                plugin_id="github",
                repo_external_id="me/repo",
                payload={},
                pr_id=None,
            )
        )
    )
    outcome = await ArchiveStaleFindings().execute({"stale_finding_ids": [str(uuid4())]}, _ctx())
    assert outcome.label == "success"
    assert outcome.outputs.get("archived_count") == 0


async def test_unknown_findings_are_skipped_not_failed(
    db_session, workflow_context_provider_isolation
) -> None:  # type: ignore[no-untyped-def]
    """pr_id present but the listed finding_ids aren't in the aggregate
    (hard-deleted, or stale payload from upstream) → all skipped, success
    with archived_count=0 and skipped_count=len(input)."""
    pr_id = uuid4()
    org_id = uuid4()
    register_workflow_context_provider(
        _StaticProvider(
            context=WorkspaceTicketContext(
                org_id=org_id,
                plugin_id="github",
                repo_external_id="me/repo",
                payload={},
                pr_id=pr_id,
            )
        )
    )
    unknown = [str(uuid4()), str(uuid4()), "not-a-uuid"]
    outcome = await ArchiveStaleFindings().execute({"stale_finding_ids": unknown}, _ctx())
    assert outcome.label == "success"
    assert outcome.outputs.get("archived_count") == 0
    assert outcome.outputs.get("skipped_count") == 3
