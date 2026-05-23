"""domain/notifications — cross-org user inbox (M06)."""

from app.domain.notifications import web  # noqa: F401
from app.domain.notifications.models import NotificationRow
from app.domain.notifications.service import (
    Notification,
    list_for_user,
    mark_all_read,
    mark_read,
    popover_for_user,
    record,
)

__all__ = [
    "Notification",
    "NotificationRow",
    "list_for_user",
    "mark_all_read",
    "mark_read",
    "popover_for_user",
    "record",
]
