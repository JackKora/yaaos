"""Wrapper plugin that fakes any `CodingAgentPlugin` for offline tests.

The bootstrap (when `YAAOS_CODING_AGENT_STUB` is set) walks the
`domain/coding_agent` registry and replaces each registered plugin with a
`StubCodingAgentPlugin` wrapping it. From every consumer's perspective, nothing
changes — `coding_agent.review(...)` returns the same `ReviewResult` shape; it
just never touches a real CLI or vendor API.

The stub returns canned success results. It has zero knowledge of prompt
content — that's the real plugin's responsibility. `validate_config` passes
through; `health_check` reports stub mode.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from app.core.workspace import Workspace
from app.domain.coding_agent import (
    HealthStatus,
    InvocationStatus,
    InvocationTelemetry,
    ReviewContext,
    ReviewResult,
    ValidationResult,
)
from app.domain.vcs import Finding

log = structlog.get_logger("testing.stub_coding_agent")


_STUB_TELEMETRY = InvocationTelemetry(
    tokens_in=1000,
    tokens_out=200,
    cost_usd=Decimal("0.0050"),
    latency_ms=10,
    raw_output="",
    raw_stderr="",
)


class StubCodingAgentPlugin:
    """Wraps a real `CodingAgentPlugin`; intercepts `review`."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped
        self.meta = wrapped.meta

    async def review(self, workspace: Workspace, context: ReviewContext) -> ReviewResult:
        del workspace
        # Emit one synthetic finding tagged with a subagent so e2e flows that
        # depend on findings have something to act against.
        finding = Finding(
            file="src/example.ts",
            line_start=1,
            line_end=1,
            severity="suggestion",
            title="[stub] sample suggestion",
            body="Stub finding. Used by e2e specs that exercise the finding-expansion + Teach-yaaos flow.",
            rationale=None,
            snippet=None,
            applied_lesson_ids=[],
            source_agent="yaaos-architecture",
        )
        return ReviewResult(
            status=InvocationStatus.SUCCESS,
            findings=[finding],
            state="COMMENT",
            summary_body="[stub] yaaos review",
            lesson_ids_consulted=[lesson.id for lesson in context.lessons],
            telemetry=_STUB_TELEMETRY,
        )

    async def validate_config(self, agent_config: dict[str, Any]) -> ValidationResult:
        return await self._wrapped.validate_config(agent_config)

    async def health_check(self) -> HealthStatus:
        return HealthStatus(healthy=True, message="stub mode", checked_at=datetime.now(UTC))


def wrap_all_registered_plugins() -> int:
    """Replace every entry in `domain.coding_agent._PLUGINS` with a stub wrapping it."""
    from app.domain.coding_agent import _PLUGINS  # noqa: PLC0415 — registry access

    count = 0
    for plugin_id, real in list(_PLUGINS.items()):
        if isinstance(real, StubCodingAgentPlugin):
            continue  # idempotent
        _PLUGINS[plugin_id] = StubCodingAgentPlugin(wrapped=real)
        count += 1
    log.info("stub_coding_agent.wrapped_all", count=count)
    return count
