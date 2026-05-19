"""Phase 13 — startup secret-hygiene check."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def prod_env(monkeypatch):
    monkeypatch.setenv("YAAOS_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql+asyncpg://x/y"))
    monkeypatch.setenv("YAAOS_ENCRYPTION_KEY", "VHJ5SW5nTm90VG9CcmVha1lvdXJTZWNyZXRzS2V5MTIzPQ==")
    from app.core.config.service import get_settings  # noqa: PLC0415

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_prod_with_stub_secrets_raises(prod_env, monkeypatch):
    # Leave all M02 secrets at their dev defaults.
    monkeypatch.delenv("YAAOS_OAUTH_GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("YAAOS_OAUTH_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YAAOS_TOTP_MASTER_KEY", raising=False)
    from app.core.config.service import get_settings  # noqa: PLC0415

    get_settings.cache_clear()
    from app.core.webserver.app_factory import _check_required_prod_secrets  # noqa: PLC0415

    with pytest.raises(RuntimeError, match="refuses to start in prod"):
        _check_required_prod_secrets()


def test_prod_with_all_secrets_set_does_not_raise(prod_env, monkeypatch):
    monkeypatch.setenv("YAAOS_OAUTH_STATE_SECRET", "real-state-secret")
    monkeypatch.setenv("YAAOS_INVITATION_TOKEN_SECRET", "real-invitation-secret")
    monkeypatch.setenv("YAAOS_OAUTH_GITHUB_CLIENT_ID", "real-id")
    monkeypatch.setenv("YAAOS_OAUTH_GITHUB_CLIENT_SECRET", "real-secret")
    monkeypatch.setenv("YAAOS_TOTP_MASTER_KEY", "VHJ5SW5nTm90VG9CcmVha1lvdXJTZWNyZXRzS2V5MTIzPQ==")
    from app.core.config.service import get_settings  # noqa: PLC0415

    get_settings.cache_clear()
    from app.core.webserver.app_factory import _check_required_prod_secrets  # noqa: PLC0415

    _check_required_prod_secrets()  # should not raise


def test_non_prod_skip_check(monkeypatch):
    monkeypatch.setenv("YAAOS_ENV", "dev")
    from app.core.config.service import get_settings  # noqa: PLC0415

    get_settings.cache_clear()
    from app.core.webserver.app_factory import _check_required_prod_secrets  # noqa: PLC0415

    _check_required_prod_secrets()  # dev should be lenient
    get_settings.cache_clear()
