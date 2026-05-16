"""Types + Protocol for the coding-agent abstraction."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from app.core.workspace import HealthStatus, Workspace


class AgentInvocationStatus(StrEnum):
    SUCCESS = "success"
    PARSE_FAILURE = "parse_failure"
    AGENT_ERROR = "agent_error"
    TIMEOUT = "timeout"


T = TypeVar("T", bound=BaseModel)


class AgentSpec(BaseModel):
    name: str
    prompt_text: str
    coding_agent_plugin_id: str
    agent_config: dict[str, Any] = {}


class AgentInvocationResult[T: BaseModel](BaseModel):
    status: AgentInvocationStatus
    parsed: T | None = None
    raw_output: str = ""
    raw_stderr: str = ""
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: Decimal | None = None
    latency_ms: int = 0
    error_message: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []


class CodingAgentPlugin(Protocol):
    plugin_id: str

    async def invoke(
        self,
        workspace: Workspace,
        prompt: str,
        agent_config: dict[str, Any],
        response_model: type[BaseModel],
    ) -> AgentInvocationResult[Any]: ...

    async def validate_config(self, agent_config: dict[str, Any]) -> ValidationResult: ...

    async def health_check(self) -> HealthStatus: ...


class CodingAgentError(Exception):
    """Infrastructure failure (subprocess won't spawn, config table unreadable)."""


class PluginNotFoundError(LookupError):
    """Plugin id not registered."""


class CodingAgentCacheMiss(Exception):
    """Raised by the caching wrapper when a cached invocation is missing in pytest."""
