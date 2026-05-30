"""Fail-fast contract for the workflow-context provider slot.

`get_workflow_context_provider()` raises when no provider is bound —
a missing provider is a boot-time wiring bug, not a runtime option.
`assert_workflow_context_provider()` is the startup-check entry point
(called from web.py / worker.py after domain/reviewer import).
"""

from __future__ import annotations

import pytest

from app.core.workspace.workflow_context import (
    assert_workflow_context_provider,
    get_workflow_context_provider,
    register_workflow_context_provider,
)


class _StubProvider:
    async def get_workspace_ticket_context(self, ticket_id):  # type: ignore[no-untyped-def]
        del ticket_id
        return None


def test_get_raises_when_unbound(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """With no provider registered, get_workflow_context_provider raises RuntimeError."""
    del workflow_context_provider_isolation
    with pytest.raises(RuntimeError, match="workflow_context provider not registered"):
        get_workflow_context_provider()


def test_assert_raises_when_unbound(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """assert_workflow_context_provider() raises when no provider is installed."""
    del workflow_context_provider_isolation
    with pytest.raises(RuntimeError, match="workflow_context provider not registered"):
        assert_workflow_context_provider()


def test_get_returns_non_null_after_register(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """After registering a provider, get_workflow_context_provider returns it (non-None)."""
    del workflow_context_provider_isolation
    stub = _StubProvider()
    register_workflow_context_provider(stub)
    result = get_workflow_context_provider()
    assert result is stub


def test_assert_succeeds_after_register(workflow_context_provider_isolation) -> None:  # type: ignore[no-untyped-def]
    """assert_workflow_context_provider() does not raise when a provider is installed."""
    del workflow_context_provider_isolation
    register_workflow_context_provider(_StubProvider())
    assert_workflow_context_provider()  # must not raise
