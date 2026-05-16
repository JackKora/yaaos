"""Tests for stub mode and validate_config — no DB / CLI needed."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.core.coding_agent import AgentInvocationStatus, ValidationResult
from app.plugins.claude_code import get_plugin


class _Finding(BaseModel):
    severity: str
    title: str
    body: str
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    rationale: str | None = None
    snippet: list[dict] | None = None
    applied_lesson_ids: list[str] = []


class _FindingList(BaseModel):
    findings: list[_Finding]


@pytest.fixture(autouse=True)
def _enable_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YAAOF_CODING_AGENT_STUB", "1")


class _FakeWS:
    id = "fake"
    working_dir = "/tmp/fake"

    async def info(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError


@pytest.mark.asyncio
async def test_stub_returns_findings_for_architecture() -> None:
    plugin = get_plugin()
    prompt = "# Agent: architecture\n\nReview this PR..."
    result = await plugin.invoke(_FakeWS(), prompt, {}, _FindingList)
    assert result.status == AgentInvocationStatus.SUCCESS
    assert result.parsed is not None
    assert len(result.parsed.findings) >= 1
    assert result.parsed.findings[0].severity in {"suggestion", "info", "nit", "must-fix"}


@pytest.mark.asyncio
async def test_stub_returns_security_findings() -> None:
    plugin = get_plugin()
    prompt = "# Agent: security\n\nReview this PR..."
    result = await plugin.invoke(_FakeWS(), prompt, {}, _FindingList)
    assert result.status == AgentInvocationStatus.SUCCESS


@pytest.mark.asyncio
async def test_validate_config_rejects_unknown_keys() -> None:
    res: ValidationResult = await get_plugin().validate_config({"badkey": 1})
    assert not res.valid
    assert any("badkey" in e for e in res.errors)


@pytest.mark.asyncio
async def test_validate_config_rejects_bad_timeout() -> None:
    res = await get_plugin().validate_config({"timeout_seconds": -1})
    assert not res.valid


@pytest.mark.asyncio
async def test_validate_config_accepts_empty() -> None:
    res = await get_plugin().validate_config({})
    assert res.valid


@pytest.mark.asyncio
async def test_health_check_in_stub_mode_is_healthy() -> None:
    h = await get_plugin().health_check()
    assert h.healthy
