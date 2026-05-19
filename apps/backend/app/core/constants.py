"""Centralised constants whose values are referenced from multiple modules.

Single source of truth so changes propagate without grep-and-pray. Keep this
file tiny — when a constant belongs to a specific module's contract, prefer
defining it there.
"""

from __future__ import annotations

from datetime import timedelta

# M02 — audit-log retention. The periodic cleanup task in
# `domain/identity/scheduler.py` purges `audit_entries` rows older than this.
AUDIT_LOG_RETENTION = timedelta(days=30)


__all__ = ["AUDIT_LOG_RETENTION"]
