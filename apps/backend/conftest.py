"""Top-level pytest fixtures shared across all backend module tests."""

import os
import warnings

import pytest

# Set test env vars BEFORE any app imports so module-level `get_settings()` works.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://yaaof:yaaof@localhost:5432/yaaof_test")
os.environ.setdefault("YAAOF_ENCRYPTION_KEY", "vrGOcrqpNIMof1qsuwOEVYvgxo-03dCX8lfVXm_G4JI=")
os.environ.setdefault("YAAOF_ENV", "dev")
os.environ.setdefault("YAAOF_CODING_AGENT_STUB", "1")
os.environ.setdefault("YAAOF_REVIEW_DEBOUNCE_SECONDS", "0")
os.environ.setdefault("YAAOF_REAPER_INTERVAL_SECONDS", "1")
os.environ.setdefault("YAAOF_HEARTBEAT_INTERVAL_SECONDS", "1")
os.environ.setdefault("YAAOF_CATCHUP_DELAY_SECONDS", "0")


@pytest.fixture(scope="session", autouse=True)
def _quiet_pydantic_warnings() -> None:
    """Suppress noisy pydantic deprecation warnings during tests."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic.*")
