"""Pydantic settings model for the `claude_code` coding-agent plugin.

Lives in the plugin (not `domain/orgs`) because the schema is intimately
tied to the plugin's runtime contract. `domain/orgs.install_coding_agent`
calls `validate_settings()` via the plugin's `Plugin.validate_settings`
hook, which delegates here. The settings JSONB shape is:

    {orchestrator: AgentSettings, agents: [AgentSettings, ...]}

Constraints (Phase 10):
- Sub-agent count: 1 ≤ len(agents) ≤ 8.
- Sub-agent names: unique within `agents`, length 1..64.
- model, version, effort: must be from the enum lists in `defaults.py`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.plugins.claude_code.defaults import EFFORTS, MODELS, VERSIONS


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1)
    model: str
    version: str
    effort: str
    updated_at: str = ""

    @field_validator("model")
    @classmethod
    def _model_in_enum(cls, v: str) -> str:
        if v not in MODELS:
            raise ValueError(f"model must be one of {list(MODELS)}")
        return v

    @field_validator("version")
    @classmethod
    def _version_in_enum(cls, v: str) -> str:
        if v not in VERSIONS:
            raise ValueError(f"version must be one of {list(VERSIONS)}")
        return v

    @field_validator("effort")
    @classmethod
    def _effort_in_enum(cls, v: str) -> str:
        if v not in EFFORTS:
            raise ValueError(f"effort must be one of {list(EFFORTS)}")
        return v


class ClaudeCodeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orchestrator: AgentSettings
    agents: list[AgentSettings] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def _unique_agent_names(self) -> ClaudeCodeSettings:
        names = [a.name for a in self.agents]
        if len(names) != len(set(names)):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"sub-agent names must be unique; duplicates: {duplicates}")
        return self


def validate_settings(raw: dict[str, Any]) -> dict[str, Any]:
    """Public validator used by `ClaudeCodePlugin.validate_settings`. Returns
    a normalized dict; raises `ValueError` (with Pydantic detail attached
    via `__cause__`) on invalid input."""
    try:
        parsed = ClaudeCodeSettings.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError subclasses Exception
        raise ValueError(str(exc)) from exc
    return parsed.model_dump(mode="python")
