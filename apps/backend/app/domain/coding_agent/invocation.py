"""Builds the `invocation` block of the `InvokeClaudeCode` AgentCommand
payload for each of the five reviewer task modes.

The wire-layer `InvokeClaudeCodeCommand.invocation` is `dict[str, Any]` —
intentionally permissive because shape ownership is in `domain/coding_agent`,
not the wire. This module is that owner.

The Go agent unmarshals the dict into its own per-mode struct and dispatches
it through its plugin abstraction. The control plane (here) builds it from
the typed context object the Python reviewer command already has.

Shape:

    {
        "mode": "review" | "incremental_review" | "verify_fix" | "stale_check" | "answer_question",
        "context": <FooContext.model_dump()>,
        "prompt_config": {
            "model": "opus" | "sonnet",
            "effort": "low" | "medium" | "high",
        },
    }

`prompt_config` defaults match `plugins/claude_code` (`_DEFAULT_MODEL`,
`_DEFAULT_EFFORT`). Callers pass an override when an org/agent config
customizes them. Future per-org agent_config rows replace these defaults.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.domain.coding_agent.types import (
    AnswerQuestionContext,
    IncrementalReviewContext,
    ReviewContext,
    StaleCheckContext,
    VerifyFixContext,
)

InvocationMode = Literal["review", "incremental_review", "verify_fix", "stale_check", "answer_question"]

# Defaults match `plugins/claude_code`'s `_DEFAULT_MODEL` / `_DEFAULT_EFFORT`.
# Kept here so callers don't need to import the plugin (Tach layering).
_DEFAULT_MODEL = "opus"
_DEFAULT_EFFORT = "medium"


# The five typed contexts the build_invocation function accepts. Each
# command body picks the one that matches its `mode`.
_Context = (
    ReviewContext | IncrementalReviewContext | VerifyFixContext | StaleCheckContext | AnswerQuestionContext
)


def build_invocation(
    *,
    mode: InvocationMode,
    context: _Context,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    """Build the `invocation` dict for `InvokeClaudeCodeCommand.invocation`.

    `context`: one of the five typed `<Mode>Context` Pydantic models. Its
    `.model_dump(mode="json")` is what crosses the wire — must already be
    JSON-serializable end-to-end (the types enforce this).

    `model` / `effort`: override the per-org defaults when the caller has
    org-specific config; else falls through to the constants matching the
    `plugins/claude_code` defaults.
    """
    if not isinstance(context, BaseModel):
        raise TypeError(f"context must be a Pydantic BaseModel, got {type(context).__name__}")
    return {
        "mode": mode,
        "context": context.model_dump(mode="json"),
        "prompt_config": {
            "model": model or _DEFAULT_MODEL,
            "effort": effort or _DEFAULT_EFFORT,
        },
    }


__all__ = ["InvocationMode", "build_invocation"]
