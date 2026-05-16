"""testing/stub_coding_agent — wrapper plugin that fakes any CodingAgentPlugin."""

from app.testing.stub_coding_agent.service import (
    StubCodingAgentPlugin,
    wrap_all_registered_plugins,
)

__all__ = ["StubCodingAgentPlugin", "wrap_all_registered_plugins"]
