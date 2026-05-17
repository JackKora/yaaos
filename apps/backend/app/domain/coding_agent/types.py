"""Types + Protocol for the coding-agent abstraction.

The Protocol exposes one operation — `review(context)` — not a generic
`invoke(prompt, response_model)`. Consumers hand over domain inputs (a PR,
a diff, lessons) and receive vendor-neutral results. Prompt assembly,
output-schema definition, and JSON parsing are the plugin's job.

The plugin is expected to spawn a single parent reviewer that dispatches
subagent definitions (shipped under `app/domain/coding_agent/reviewers/`)
and synthesizes their findings — the plugin owns the orchestration shape,
not the contract.

Lives in `domain/` (not `core/`) because its types reference `vcs.Finding` and
related domain models. The plugin contract resolves through a registry.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from app.core.primitives import PluginMeta
from app.core.workspace import HealthStatus, Workspace
from app.domain.memory import Lesson
from app.domain.vcs import Diff, Finding, VCSPullRequest


class InvocationStatus(StrEnum):
    SUCCESS = "success"
    PARSE_FAILURE = "parse_failure"
    AGENT_ERROR = "agent_error"
    TIMEOUT = "timeout"


class InvocationTelemetry(BaseModel):
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: Decimal | None = None
    latency_ms: int = 0
    raw_output: str = ""
    raw_stderr: str = ""


class ReviewContext(BaseModel):
    """Everything a plugin needs to produce a review of a PR.

    There's no per-agent persona anymore — the plugin spawns a single parent
    reviewer that dispatches subagents whose definitions ship with yaaos.
    """

    pr: VCSPullRequest
    diff: Diff
    lessons: list[Lesson] = []
    language_hint: str | None = None
    prior_yaaos_comment_bodies: list[str] = []
    agent_config: dict[str, Any] = {}


class ReviewResult(BaseModel):
    status: InvocationStatus
    findings: list[Finding] = []
    state: Literal["APPROVED", "CHANGES_REQUESTED", "COMMENT"] | None = None
    summary_body: str | None = None
    lesson_ids_consulted: list[UUID] = []
    telemetry: InvocationTelemetry = InvocationTelemetry()
    error_message: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []


class CodingAgentPlugin(Protocol):
    meta: PluginMeta

    async def review(self, workspace: Workspace, context: ReviewContext) -> ReviewResult: ...

    async def validate_config(self, agent_config: dict[str, Any]) -> ValidationResult: ...

    async def health_check(self) -> HealthStatus: ...


class CodingAgentError(Exception):
    """Infrastructure failure (subprocess won't spawn, config table unreadable)."""


class PluginNotFoundError(LookupError):
    """Plugin id not registered."""


class CodingAgentCacheMiss(Exception):
    """Raised by the caching wrapper when a cached invocation is missing in pytest."""
