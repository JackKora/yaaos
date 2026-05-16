"""Prompt assembly + verdict computation — pure helpers."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.memory import Lesson
from app.domain.reviewer.finding_types import FindingDto


def assemble_prompt(
    *,
    agent_name: str,
    agent_prompt_text: str,
    diff_raw: str,
    lessons: Iterable[Lesson],
    language_hint: str | None,
    prior_yaaof_comment_bodies: list[str],
    pr_title: str,
    pr_body: str | None,
) -> str:
    parts: list[str] = [
        f"# Agent: {agent_name}",
        "",
        agent_prompt_text.strip(),
        "",
    ]
    if language_hint:
        parts.extend(
            [
                "## Repository language",
                f"This repository is primarily {language_hint}.",
                "",
            ]
        )
    parts.extend(
        [
            "## Pull request",
            f"### Title\n{pr_title}",
            f"### Description\n{pr_body or '(no description)'}",
            "",
            "## Diff",
            "```diff",
            diff_raw.strip() or "(no diff)",
            "```",
        ]
    )
    lesson_list = list(lessons)
    if lesson_list:
        parts.extend(
            [
                "",
                "## Lessons learned from past reviews",
                "Apply these when reviewing this PR.",
                "",
            ]
        )
        for l in lesson_list:
            parts.append(f"### {l.title}\n_lesson_id: {l.id}_\n{l.body}")
    if prior_yaaof_comment_bodies:
        parts.extend(
            [
                "",
                "## Prior comments from sibling review agents",
                "Don't duplicate them; build on or disagree.",
                "",
            ]
        )
        for body in prior_yaaof_comment_bodies[:20]:
            parts.append(f"- {body[:200]}")
    return "\n".join(parts)


def compute_verdict(findings: list[FindingDto]) -> str:
    """Returns 'APPROVED' | 'CHANGES_REQUESTED' | 'COMMENT'."""
    if not findings:
        return "APPROVED"
    if any(f.severity == "must-fix" for f in findings):
        return "CHANGES_REQUESTED"
    return "COMMENT"
