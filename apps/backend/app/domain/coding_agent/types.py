"""Types + Protocol for the coding-agent abstraction.

The Protocol exposes targeted operations — `review(context)` and `reply(context)` —
not a generic `invoke(prompt, response_model)`. Consumers hand over domain inputs
(a PR, a diff, lessons, a persona) and receive vendor-neutral results. Prompt
assembly, output-schema definition, and JSON parsing are the plugin's job.

Lives in `domain/` (not `core/`) because its types reference `vcs.Finding` and
related domain models. The plugin contract still resolves through a registry,
same shape as before.
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


class AgentSpec(BaseModel):
    name: str
    prompt_text: str
    coding_agent_plugin_id: str
    agent_config: dict[str, Any] = {}


class ReviewContext(BaseModel):
    """Everything a plugin needs to produce a review.

    `persona` is the agent row's `prompt_text` — focus/role instructions the
    plugin weaves into its own review prompt. The plugin owns the structural
    framing (system message, output schema, etc.); the persona is content.
    """

    persona: str
    agent_name: str
    pr: VCSPullRequest
    diff: Diff
    lessons: list[Lesson] = []
    language_hint: str | None = None
    prior_yaaos_comment_bodies: list[str] = []
    agent_config: dict[str, Any] = {}


class ReplyContext(BaseModel):
    persona: str
    agent_name: str
    pr: VCSPullRequest
    diff: Diff
    reply_body: str
    parent_comment_external_id: str
    agent_config: dict[str, Any] = {}


class ReviewResult(BaseModel):
    status: InvocationStatus
    findings: list[Finding] = []
    state: Literal["APPROVED", "CHANGES_REQUESTED", "COMMENT"] | None = None
    summary_body: str | None = None
    lesson_ids_consulted: list[UUID] = []
    telemetry: InvocationTelemetry = InvocationTelemetry()
    error_message: str | None = None


class ReplyResult(BaseModel):
    status: InvocationStatus
    body: str | None = None
    telemetry: InvocationTelemetry = InvocationTelemetry()
    error_message: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []


class CodingAgentPlugin(Protocol):
    meta: PluginMeta

    async def review(self, workspace: Workspace, context: ReviewContext) -> ReviewResult: ...

    async def reply(self, workspace: Workspace, context: ReplyContext) -> ReplyResult: ...

    async def validate_config(self, agent_config: dict[str, Any]) -> ValidationResult: ...

    async def health_check(self) -> HealthStatus: ...


class CodingAgentError(Exception):
    """Infrastructure failure (subprocess won't spawn, config table unreadable)."""


class PluginNotFoundError(LookupError):
    """Plugin id not registered."""


class CodingAgentCacheMiss(Exception):
    """Raised by the caching wrapper when a cached invocation is missing in pytest."""
