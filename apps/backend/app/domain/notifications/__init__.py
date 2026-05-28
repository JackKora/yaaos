"""domain/notifications — cross-org user inbox."""

from app.domain.notifications import web  # noqa: F401
from app.domain.notifications.service import (
    Notification,
    list_for_user,
    mark_all_read,
    mark_read,
    popover_for_user,
    record,
)
from app.domain.notifications.tasks import handle_ticket_status_change

__all__ = [
    "Notification",
    "handle_ticket_status_change",
    "list_for_user",
    "mark_all_read",
    "mark_read",
    "popover_for_user",
    "record",
]
