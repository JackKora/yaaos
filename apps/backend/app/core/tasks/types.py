"""Shared types for the task pipeline.

`TaskMetadata` is the typed envelope carried on the taskiq label
`metadata` from `enqueue` (producer) through the outbox + drain to
`OrgContextMiddleware` (consumer). Replaces the prior dict-via-repr
encoding: producer dumps via `model_dump_json()`, consumer parses via
`model_validate_json()` — JSON in/out, no `ast.literal_eval` round-trip.

Tests that call `pre_execute` directly with a raw dict still work —
`model_validate` accepts both dict and JSON-string inputs.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TaskMetadata(BaseModel):
    """Per-task envelope. `org_id` ties the task to an org so the worker
    can enter `org_context` before the body runs.
    """

    model_config = {"frozen": True}

    org_id: UUID
