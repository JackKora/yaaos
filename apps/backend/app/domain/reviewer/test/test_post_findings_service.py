"""`PostFindings` — persists `ReportedFinding`s through `publish_findings`.

Covers the defensive branches that don't require a workspace + aggregate
fixture. Happy-path (ReportedFinding → FindingRow) rides on the
`test_post_findings_happy_path.py` coverage; this slice verifies the
wrapper's edge cases.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.workflow import CommandContext
from app.domain.reviewer.commands import PostFindings


def _ctx() -> CommandContext:
    return CommandContext(
        workflow_execution_id=str(uuid4()),
        ticket_id=str(uuid4()),
        step_id="post",
        attempt=0,
    )


async def test_empty_drafts_returns_success_zero_count(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """No draft_findings → success-no-op before reaching the DB."""
    outcome = await PostFindings().execute({}, _ctx())
    assert outcome.label == "success"
    assert outcome.outputs.get("admitted_count") == 0


async def test_invalid_reported_finding_payload_returns_failure(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """Malformed draft dict (missing required fields) → failure with explanation."""
    outcome = await PostFindings().execute(
        {"draft_findings": [{"not_a_field": "x"}]},
        _ctx(),
    )
    assert outcome.label == "failure"
    assert "invalid ReportedFinding" in (outcome.failure_reason or "")
