"""Recovery-policy registry tests — registry lives in core/workflow."""

from __future__ import annotations

import pytest

import app.core.workspace  # noqa: F401  — side-effect: workspace import (registration now explicit)
from app.core.workflow import register_recovery_policy
from app.core.workflow.recovery import get_recovery_policy, registered_recovery_labels


@pytest.fixture(autouse=True)
def _isolate(recovery_policies_isolation) -> None:  # type: ignore[no-untyped-def]
    del recovery_policies_isolation  # fixture handles clear before+after


def test_register_and_get() -> None:
    register_recovery_policy(failure_label="auth_expired", command_kind="RefreshWorkspaceAuth")
    assert get_recovery_policy("auth_expired") == "RefreshWorkspaceAuth"


def test_unknown_label_returns_none() -> None:
    assert get_recovery_policy("no_such_label") is None


def test_register_idempotent_same_target() -> None:
    register_recovery_policy(failure_label="auth_expired", command_kind="RefreshWorkspaceAuth")
    register_recovery_policy(failure_label="auth_expired", command_kind="RefreshWorkspaceAuth")
    assert get_recovery_policy("auth_expired") == "RefreshWorkspaceAuth"


def test_register_conflicting_target_raises() -> None:
    register_recovery_policy(failure_label="auth_expired", command_kind="RefreshWorkspaceAuth")
    with pytest.raises(ValueError, match="already maps to"):
        register_recovery_policy(failure_label="auth_expired", command_kind="DifferentCommand")


def test_registered_recovery_labels_sorted() -> None:
    register_recovery_policy(failure_label="z_label", command_kind="ZCommand")
    register_recovery_policy(failure_label="a_label", command_kind="ACommand")
    labels = registered_recovery_labels()
    assert labels == sorted(labels)
    assert "z_label" in labels
    assert "a_label" in labels


def test_auth_expired_policy_resolves_after_explicit_registration() -> None:
    """Workspace recovery policies are registered via an explicit startup call.
    After calling `register_workspace_recovery_policies()`, the auth_expired
    label resolves to RefreshWorkspaceAuth."""
    from app.core.workspace import register_workspace_recovery_policies  # noqa: PLC0415

    register_workspace_recovery_policies()
    assert get_recovery_policy("auth_expired") == "RefreshWorkspaceAuth"
