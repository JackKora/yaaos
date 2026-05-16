"""Registry + dispatch tests for `domain/coding_agent`."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.core.primitives import PluginMeta
from app.domain.coding_agent import (
    HealthStatus,
    InvocationStatus,
    InvocationTelemetry,
    PluginNotFoundError,
    ReplyContext,
    ReplyResult,
    ReviewContext,
    ReviewResult,
    ValidationResult,
    _reset_plugins_for_tests,
    get_plugin,
    health_check_all,
    register_coding_agent_plugin,
    registered_plugin_ids,
    reply,
    review,
    validate_config,
)


class _StubPlugin:
    meta = PluginMeta(id="stub", type="coding_agent", display_name="Stub")

    async def review(self, workspace: Any, context: ReviewContext) -> ReviewResult:
        return ReviewResult(
            status=InvocationStatus.SUCCESS,
            findings=[],
            state="APPROVED",
            summary_body=f"reviewed by {context.agent_name}",
            telemetry=InvocationTelemetry(tokens_in=1, tokens_out=2, cost_usd=Decimal("0.001"), latency_ms=5),
        )

    async def reply(self, workspace: Any, context: ReplyContext) -> ReplyResult:
        return ReplyResult(
            status=InvocationStatus.SUCCESS,
            body=f"reply to {context.reply_body}",
            telemetry=InvocationTelemetry(latency_ms=3),
        )

    async def validate_config(self, agent_config: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True, errors=[])

    async def health_check(self) -> HealthStatus:
        return HealthStatus(healthy=True, message="ok", checked_at=datetime.now(UTC))


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_plugins_for_tests()
    yield
    _reset_plugins_for_tests()


def test_register_and_get_plugin() -> None:
    plugin = _StubPlugin()
    register_coding_agent_plugin(plugin)
    assert get_plugin("stub") is plugin
    assert "stub" in registered_plugin_ids()


def test_register_duplicate_raises() -> None:
    register_coding_agent_plugin(_StubPlugin())
    with pytest.raises(ValueError, match="already registered"):
        register_coding_agent_plugin(_StubPlugin())


def test_get_unknown_plugin_raises() -> None:
    with pytest.raises(PluginNotFoundError):
        get_plugin("nope")


@pytest.mark.asyncio
async def test_review_dispatch() -> None:
    from app.domain.vcs import Diff, VCSPullRequest  # noqa: PLC0415

    register_coding_agent_plugin(_StubPlugin())

    pr = VCSPullRequest(
        plugin_id="github",
        external_id="acme/web#1",
        repo_external_id="acme/web",
        number=1,
        title="t",
        body=None,
        author_login="alice",
        author_type="user",
        base_branch="main",
        head_branch="feat",
        base_sha="b",
        head_sha="h",
        is_draft=False,
        is_fork=False,
        state="open",
        html_url="http://x",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    ctx = ReviewContext(
        persona="focus on architecture",
        agent_name="architecture",
        pr=pr,
        diff=Diff(raw="", files=[]),
        lessons=[],
    )
    result = await review("stub", workspace=None, context=ctx)  # type: ignore[arg-type]
    assert result.status == InvocationStatus.SUCCESS
    assert result.state == "APPROVED"
    assert "architecture" in (result.summary_body or "")


@pytest.mark.asyncio
async def test_reply_dispatch() -> None:
    from app.domain.vcs import Diff, VCSPullRequest  # noqa: PLC0415

    register_coding_agent_plugin(_StubPlugin())
    pr = VCSPullRequest(
        plugin_id="github",
        external_id="acme/web#1",
        repo_external_id="acme/web",
        number=1,
        title="t",
        body=None,
        author_login="alice",
        author_type="user",
        base_branch="main",
        head_branch="feat",
        base_sha="b",
        head_sha="h",
        is_draft=False,
        is_fork=False,
        state="open",
        html_url="http://x",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    ctx = ReplyContext(
        persona="be terse",
        agent_name="security",
        pr=pr,
        diff=Diff(raw="", files=[]),
        reply_body="hi",
        parent_comment_external_id="c1",
    )
    result = await reply("stub", workspace=None, context=ctx)  # type: ignore[arg-type]
    assert result.status == InvocationStatus.SUCCESS
    assert result.body == "reply to hi"


@pytest.mark.asyncio
async def test_validate_config_dispatch() -> None:
    register_coding_agent_plugin(_StubPlugin())
    res = await validate_config("stub", {})
    assert res.valid is True


@pytest.mark.asyncio
async def test_health_check_all_handles_plugin_exception() -> None:
    class _Broken:
        meta = PluginMeta(id="broken", type="coding_agent", display_name="Broken")

        async def review(self, *a, **kw):
            raise NotImplementedError

        async def reply(self, *a, **kw):
            raise NotImplementedError

        async def validate_config(self, *a, **kw):
            return ValidationResult(valid=True, errors=[])

        async def health_check(self) -> HealthStatus:
            raise RuntimeError("boom")

    register_coding_agent_plugin(_Broken())
    out = await health_check_all()
    assert out["broken"].healthy is False
    assert "boom" in out["broken"].message
