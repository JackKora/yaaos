"""Stub wrapper tests — no DB, no subprocess, no env."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from app.core.coding_agent import (
    AgentInvocationResult,
    AgentInvocationStatus,
    HealthStatus,
    ValidationResult,
)
from app.testing.stub_coding_agent import (
    StubCodingAgentPlugin,
    wrap_all_registered_plugins,
)


class _DummyResponse(BaseModel):
    answer: str
    score: int = 0


class _DummyPlugin:
    plugin_id = "dummy"

    async def invoke(self, *args, **kwargs) -> AgentInvocationResult[Any]:
        raise AssertionError("real invoke must not be called when wrapped")

    async def validate_config(self, agent_config: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True, errors=[])

    async def health_check(self) -> HealthStatus:
        return HealthStatus(healthy=True, message="real ok", checked_at=datetime.now(UTC))


class _FakeWorkspace:
    id = "fake"
    working_dir = "/tmp/fake"

    async def info(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError


@pytest.mark.asyncio
async def test_invoke_returns_success_for_unknown_response_model() -> None:
    """Generic case: response_model has fields with defaults → wrapper synthesizes blank."""
    stub = StubCodingAgentPlugin(wrapped=_DummyPlugin())

    class WithDefaults(BaseModel):
        answer: str = "default"
        score: int = 0

    result = await stub.invoke(_FakeWorkspace(), "prompt", {}, WithDefaults)
    assert result.status == AgentInvocationStatus.SUCCESS
    assert isinstance(result.parsed, WithDefaults)


@pytest.mark.asyncio
async def test_invoke_synthesizes_finding_list() -> None:
    """Known shape: FindingList gets one info finding so verdict computation works."""
    from app.domain.reviewer.finding_types import FindingList  # noqa: PLC0415

    stub = StubCodingAgentPlugin(wrapped=_DummyPlugin())
    result = await stub.invoke(_FakeWorkspace(), "prompt", {}, FindingList)
    assert result.status == AgentInvocationStatus.SUCCESS
    assert result.parsed is not None
    assert len(result.parsed.findings) == 1
    assert result.parsed.findings[0].severity == "info"


@pytest.mark.asyncio
async def test_invoke_synthesizes_reply_response() -> None:
    from app.domain.reviewer.finding_types import ReplyResponse  # noqa: PLC0415

    stub = StubCodingAgentPlugin(wrapped=_DummyPlugin())
    result = await stub.invoke(_FakeWorkspace(), "prompt", {}, ReplyResponse)
    assert result.status == AgentInvocationStatus.SUCCESS
    assert result.parsed.body  # non-empty


@pytest.mark.asyncio
async def test_validate_config_passes_through() -> None:
    stub = StubCodingAgentPlugin(wrapped=_DummyPlugin())
    res = await stub.validate_config({})
    assert res.valid is True


@pytest.mark.asyncio
async def test_health_check_always_healthy_in_stub_mode() -> None:
    stub = StubCodingAgentPlugin(wrapped=_DummyPlugin())
    h = await stub.health_check()
    assert h.healthy is True
    assert "stub" in h.message.lower()


def test_plugin_id_mirrors_wrapped() -> None:
    stub = StubCodingAgentPlugin(wrapped=_DummyPlugin())
    assert stub.plugin_id == "dummy"


def test_wrap_all_is_idempotent() -> None:
    from app.core.coding_agent import _PLUGINS  # noqa: PLC0415
    from app.core.coding_agent.service import _reset_plugins_for_tests  # noqa: PLC0415

    _reset_plugins_for_tests()
    dummy = _DummyPlugin()
    _PLUGINS["dummy"] = dummy
    assert wrap_all_registered_plugins() == 1
    assert isinstance(_PLUGINS["dummy"], StubCodingAgentPlugin)
    # second call is a no-op — already wrapped
    assert wrap_all_registered_plugins() == 0
    _reset_plugins_for_tests()
