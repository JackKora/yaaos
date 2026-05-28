"""serialize_for_sse: formats a dict payload as an SSE data frame.

Pure formatter — no Redis, no Postgres needed.
"""

from __future__ import annotations

import json

import pytest

from app.core.sse import serialize_for_sse


@pytest.mark.service
def test_serialize_for_sse_formats_payload() -> None:
    """Output is exactly `data: <json>\\n\\n`."""
    payload = {"kind": "step_started", "step": "lint", "value": 42}
    result = serialize_for_sse(payload)
    assert result == f"data: {json.dumps(payload)}\n\n"
