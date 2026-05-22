"""Reviewer WorkflowCommands for the five M05 task modes.

Five **Workspace** commands wrap `domain/coding_agent` invocations against
a workspace:
- `CodeReview` — full-PR review.
- `IncrementalReview` — push-driven incremental review against a base sha.
- `VerifyFix` — ack a developer's "is this fixed?" reply on a finding.
- `StaleCheck` — periodic check that an open finding still applies.
- `AnswerQuestion` — answer a developer @yaaos-mention on a finding.

Five **Local** commands handle the control-plane side:
- `CheckShouldReview` — admission gating (draft/skip-label/external-contrib/
  org-config) before any workspace is provisioned.
- `PostFindings` — admit findings via the aggregate, post to GitHub.
- `ResolveFinding` — close a finding's thread on a verified fix.
- `ArchiveStaleFindings` — mark stale findings archived.
- `PostReply` — post a reply on a finding's thread.

`CheckShouldReview` ships with a real body that reads admission signals
(is_draft / is_fork / labels) from the ticket payload. The other four Local
commands and all five Workspace commands ship as stubs pending the queue.py
dismantle that wires the existing reviewer pipeline through them.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.core.database import session as db_session
from app.core.workflow import CommandCategory, CommandContext, Outcome
from app.domain.tickets import get_payload as get_ticket_payload

log = structlog.get_logger("domain.reviewer.commands")

# Labels whose presence on a PR force-skips the review. Matches the legacy
# `queue.py` behavior so the cutover is a straight swap. Case-insensitive.
SKIP_LABELS: frozenset[str] = frozenset({"yaaos-skip", "no-review", "wip"})

# ── Workspace commands (5) ──────────────────────────────────────────────


class _WorkspaceReviewCommand:
    """Workspace-category reviewer command. Each wraps a `domain/coding_agent`
    invocation in the full implementation."""

    category = CommandCategory.WORKSPACE
    restart_safe = True

    async def execute(self, inputs: dict[str, Any], ctx: CommandContext) -> Outcome:
        del inputs, ctx
        return Outcome.success()


class CodeReview(_WorkspaceReviewCommand):
    kind = "CodeReview"


class IncrementalReview(_WorkspaceReviewCommand):
    kind = "IncrementalReview"


class VerifyFix(_WorkspaceReviewCommand):
    kind = "VerifyFix"


class StaleCheck(_WorkspaceReviewCommand):
    kind = "StaleCheck"


class AnswerQuestion(_WorkspaceReviewCommand):
    kind = "AnswerQuestion"


# ── Local commands (5) ──────────────────────────────────────────────────


class _LocalReviewCommand:
    category = CommandCategory.LOCAL
    restart_safe = True

    async def execute(self, inputs: dict[str, Any], ctx: CommandContext) -> Outcome:
        del inputs, ctx
        return Outcome.success()


class CheckShouldReview:
    """Admission gate before provisioning. Returns `Outcome.success(label='skip')`
    when the PR is draft / fork / bot-authored / skip-labelled; workflow
    then terminates without spinning up a workspace. The PR payload (set by
    `plugins/github/intake_type`) carries `is_draft`, `is_fork`, `labels`,
    `author_login`."""

    kind = "CheckShouldReview"
    category = CommandCategory.LOCAL
    restart_safe = True

    async def execute(self, inputs: dict[str, Any], ctx: CommandContext) -> Outcome:
        del inputs
        async with db_session() as s:
            payload = await get_ticket_payload(UUID(ctx.ticket_id), session=s)

        reason = _decide_skip(payload)
        if reason is not None:
            log.info(
                "checkshouldreview.skip",
                workflow_execution_id=ctx.workflow_execution_id,
                ticket_id=ctx.ticket_id,
                reason=reason,
            )
            return Outcome.success(label="skip", outputs={"reason": reason})

        return Outcome.success(outputs={"pr_external_id": payload.get("pr_external_id")})


def _decide_skip(payload: dict[str, Any]) -> str | None:
    """First-match-wins admission. Returns a skip reason string or None for go."""
    if payload.get("is_draft"):
        return "draft"
    if payload.get("is_fork"):
        return "fork"
    labels = {str(label).lower() for label in (payload.get("labels") or [])}
    forced = labels & {label.lower() for label in SKIP_LABELS}
    if forced:
        return f"label:{sorted(forced)[0]}"
    author = (payload.get("author_login") or "").lower()
    if author.endswith("[bot]") or author.endswith("-bot"):
        return "bot_author"
    return None


class PostFindings(_LocalReviewCommand):
    kind = "PostFindings"


class ResolveFinding(_LocalReviewCommand):
    kind = "ResolveFinding"


class ArchiveStaleFindings(_LocalReviewCommand):
    kind = "ArchiveStaleFindings"


class PostReply(_LocalReviewCommand):
    kind = "PostReply"


ALL_WORKSPACE_COMMANDS: tuple[_WorkspaceReviewCommand, ...] = (
    CodeReview(),
    IncrementalReview(),
    VerifyFix(),
    StaleCheck(),
    AnswerQuestion(),
)

ALL_LOCAL_COMMANDS: tuple[object, ...] = (
    CheckShouldReview(),
    PostFindings(),
    ResolveFinding(),
    ArchiveStaleFindings(),
    PostReply(),
)


__all__ = [
    "ALL_LOCAL_COMMANDS",
    "ALL_WORKSPACE_COMMANDS",
    "AnswerQuestion",
    "ArchiveStaleFindings",
    "CheckShouldReview",
    "CodeReview",
    "IncrementalReview",
    "PostFindings",
    "PostReply",
    "ResolveFinding",
    "StaleCheck",
    "VerifyFix",
]
