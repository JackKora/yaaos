"""Pure helpers: prompt assembly + verdict computation."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.memory import Lesson
from app.domain.reviewer.finding_types import FindingDto
from app.domain.reviewer.prompt import assemble_prompt, compute_verdict


def _lesson(title: str, body: str) -> Lesson:
    now = datetime.now(UTC)
    return Lesson(
        id=uuid4(),
        org_id=uuid4(),
        repo_id=uuid4(),
        title=title,
        body=body,
        source_pr_url=None,
        created_at=now,
        updated_at=now,
    )


def test_prompt_includes_agent_header_and_diff() -> None:
    out = assemble_prompt(
        agent_name="architecture",
        agent_prompt_text="Review the changes.",
        diff_raw="diff --git a/x b/x\n+hi",
        lessons=[],
        language_hint="Python",
        prior_yaaof_comment_bodies=[],
        pr_title="T",
        pr_body=None,
    )
    assert "# Agent: architecture" in out
    assert "Python" in out
    assert "diff --git" in out


def test_prompt_includes_lessons_when_present() -> None:
    lessons = [_lesson("Avoid mocks", "Use DI instead.")]
    out = assemble_prompt(
        agent_name="security",
        agent_prompt_text="x",
        diff_raw="",
        lessons=lessons,
        language_hint=None,
        prior_yaaof_comment_bodies=[],
        pr_title="T",
        pr_body=None,
    )
    assert "Avoid mocks" in out
    assert "Use DI instead" in out
    assert "lesson_id" in out


def test_verdict_no_findings_is_approved() -> None:
    assert compute_verdict([]) == "APPROVED"


def test_verdict_must_fix_is_changes_requested() -> None:
    findings = [
        FindingDto(severity="must-fix", title="bad", body="reason"),
    ]
    assert compute_verdict(findings) == "CHANGES_REQUESTED"


def test_verdict_only_nits_is_comment() -> None:
    findings = [
        FindingDto(severity="nit", title="x", body="y"),
        FindingDto(severity="info", title="x", body="y"),
    ]
    assert compute_verdict(findings) == "COMMENT"
