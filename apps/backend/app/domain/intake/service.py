"""domain/intake — placeholder.

All GitHub event handling lives in `plugins/github.intake_type` (the single
`github` IntakeType registered with `domain/intake.registry`). This module
exists only to expose `IntakeError` for the rest of the domain layer.
"""

from __future__ import annotations


class IntakeError(Exception):
    pass
