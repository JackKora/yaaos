"""Pydantic validation: orchestrator + agents shape, enums, uniqueness, bounds."""

from __future__ import annotations

import pytest

from app.plugins.claude_code.defaults import EFFORTS, MODELS, VERSIONS, get_defaults
from app.plugins.claude_code.settings_schema import validate_settings


def _ok_orchestrator() -> dict:
    d = get_defaults()
    return d["orchestrator"]


def _ok_agent(name: str = "yaaos-architecture") -> dict:
    return {
        "name": name,
        "prompt": "do a review",
        "model": MODELS[0],
        "version": VERSIONS[0],
        "effort": EFFORTS[1],
        "updated_at": "",
    }


def test_default_settings_validate() -> None:
    d = get_defaults()
    out = validate_settings({"orchestrator": d["orchestrator"], "agents": d["agents"]})
    assert out["orchestrator"]["name"] == d["orchestrator"]["name"]
    assert len(out["agents"]) == len(d["agents"])


def test_agent_count_bounds() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        validate_settings({"orchestrator": _ok_orchestrator(), "agents": []})
    nine = [_ok_agent(f"a{i}") for i in range(9)]
    with pytest.raises(ValueError, match="at most 8"):
        validate_settings({"orchestrator": _ok_orchestrator(), "agents": nine})


def test_agent_names_must_be_unique() -> None:
    dupe = [_ok_agent("same"), _ok_agent("same")]
    with pytest.raises(ValueError, match="unique"):
        validate_settings({"orchestrator": _ok_orchestrator(), "agents": dupe})


def test_legacy_settings_without_m06_fields_still_validate() -> None:
    """Existing org_coding_agents.settings rows have no
    `use_default_system_prompt`, `system_prompt`, or `mcp_proxy_ids`. The
    M06 schema extension must accept them and supply sensible defaults."""
    out = validate_settings({"orchestrator": _ok_orchestrator(), "agents": [_ok_agent("only")]})
    assert out["orchestrator"]["use_default_system_prompt"] is True
    assert out["orchestrator"]["system_prompt"] is None
    assert out["agents"][0]["use_default_system_prompt"] is True
    assert out["agents"][0]["system_prompt"] is None
    assert out["mcp_proxy_ids"] == []


def test_m06_overrides_round_trip() -> None:
    """A settings dict that opts out of the default system prompt and supplies
    a custom one round-trips cleanly."""
    orch = _ok_orchestrator()
    orch["use_default_system_prompt"] = False
    orch["system_prompt"] = "be careful with concurrency"
    out = validate_settings({"orchestrator": orch, "agents": [_ok_agent("only")]})
    assert out["orchestrator"]["use_default_system_prompt"] is False
    assert out["orchestrator"]["system_prompt"] == "be careful with concurrency"


def test_mcp_proxy_ids_accepts_uuid_list() -> None:
    out = validate_settings(
        {
            "orchestrator": _ok_orchestrator(),
            "agents": [_ok_agent("only")],
            "mcp_proxy_ids": ["00000000-0000-0000-0000-000000000001"],
        }
    )
    assert len(out["mcp_proxy_ids"]) == 1
    # Pydantic coerces strings to UUIDs.
    assert str(out["mcp_proxy_ids"][0]) == "00000000-0000-0000-0000-000000000001"


def test_agent_name_length_capped_at_64() -> None:
    long_name = "x" * 65
    with pytest.raises(ValueError):
        validate_settings({"orchestrator": _ok_orchestrator(), "agents": [_ok_agent(long_name)]})


def test_model_enum_enforced() -> None:
    bad = {**_ok_agent(), "model": "not-a-model"}
    with pytest.raises(ValueError, match="model"):
        validate_settings({"orchestrator": _ok_orchestrator(), "agents": [bad]})


def test_effort_enum_enforced() -> None:
    bad = {**_ok_orchestrator(), "effort": "nonsense"}
    with pytest.raises(ValueError, match="effort"):
        validate_settings({"orchestrator": bad, "agents": [_ok_agent()]})


def test_unknown_top_level_keys_rejected() -> None:
    with pytest.raises(ValueError):
        validate_settings({"orchestrator": _ok_orchestrator(), "agents": [_ok_agent()], "rogue": True})
