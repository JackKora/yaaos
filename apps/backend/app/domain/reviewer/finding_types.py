"""Response models passed to coding_agent.invoke (response_model arg)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class FindingSnippetLineDto(BaseModel):
    line_number: int
    kind: Literal["context", "add", "del"]
    text: str


class FindingDto(BaseModel):
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    severity: Literal["must-fix", "nit", "suggestion", "info"]
    title: str
    body: str
    rationale: str | None = None
    snippet: list[FindingSnippetLineDto] | None = None
    applied_lesson_ids: list[UUID] = []


class FindingList(BaseModel):
    findings: list[FindingDto]


class ReplyResponse(BaseModel):
    body: str
