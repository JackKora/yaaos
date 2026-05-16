"""core/primitives — Actor + spawn helper. Bottom of the dependency tree."""

from app.core.primitives.service import Actor, ActorKind, active_task_count, spawn

__all__ = ["Actor", "ActorKind", "active_task_count", "spawn"]
