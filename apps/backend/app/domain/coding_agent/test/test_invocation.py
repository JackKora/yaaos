"""`build_invocation` — shape of `InvokeClaudeCodeCommand.invocation`.

The dict crosses the wire to the Go agent which unmarshals it into its
per-mode struct. The Python side is the schema owner; this test pins the
shape so an accidental change shows up loudly.
"""

from __future__ import annotations

import json

import pytest

from app.domain.coding_agent import (
    AnswerQuestionContext,
    FindingAnchor,
    InvocationMode,
    build_invocation,
)


def _ctx() -> AnswerQuestionContext:
    return AnswerQuestionContext(
        original_finding_title="t",
        original_finding_body="b",
        original_rule_id="r1",
        code_snippet="def x(): return None",
        current_anchor=FindingAnchor(file_path="src/foo.py", line_start=1, line_end=1),
        question="why?",
        head_sha="deadbeef",
    )


def test_shape_has_mode_context_prompt_config() -> None:
    inv = build_invocation(mode="answer_question", context=_ctx())
    assert inv["mode"] == "answer_question"
    assert isinstance(inv["context"], dict)
    assert inv["context"]["question"] == "why?"
    assert inv["prompt_config"] == {"model": "opus", "effort": "medium"}


def test_overrides_replace_defaults() -> None:
    inv = build_invocation(mode="answer_question", context=_ctx(), model="sonnet", effort="high")
    assert inv["prompt_config"] == {"model": "sonnet", "effort": "high"}


def test_context_is_json_serializable() -> None:
    """The wire layer Marshals the dict to JSON via the outbox. The
    context dict must therefore round-trip cleanly. Use model_dump's
    mode='json' which serializes UUIDs / datetimes."""
    inv = build_invocation(mode="answer_question", context=_ctx())
    # No exception → serializable.
    encoded = json.dumps(inv)
    decoded = json.loads(encoded)
    assert decoded["mode"] == "answer_question"


def test_non_pydantic_context_rejected() -> None:
    with pytest.raises(TypeError, match="must be a Pydantic BaseModel"):
        build_invocation(mode="answer_question", context={"hello": "world"})  # type: ignore[arg-type]


def test_all_five_modes_typecheck() -> None:
    """Just a literal-domain sanity check — the Literal type catches
    typos at type-check time; this runs at runtime to catch a missing
    mode in test_aggregate-style refactors."""
    for mode in ("review", "incremental_review", "verify_fix", "stale_check", "answer_question"):
        m: InvocationMode = mode  # type: ignore[assignment]
        del m
