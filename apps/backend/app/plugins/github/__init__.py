"""plugins/github — GitHub VCSPlugin + webhook receiver."""

from app.plugins.github import web  # noqa: F401 — registers webhook route
from app.plugins.github.models import (
    GitHubAppInstallationRow,
    GitHubPollerStateRow,
    GitHubSettingsRow,
    GitHubWebhookEventRow,
)
from app.plugins.github.service import (
    GitHubPlugin,
    bootstrap,
    get_plugin,
    mark_webhook_processed,
    record_webhook_event,
    verify_webhook_signature,
)

__all__ = [
    "GitHubAppInstallationRow",
    "GitHubPlugin",
    "GitHubPollerStateRow",
    "GitHubSettingsRow",
    "GitHubWebhookEventRow",
    "bootstrap",
    "get_plugin",
    "mark_webhook_processed",
    "record_webhook_event",
    "verify_webhook_signature",
]

# Register at import time.
bootstrap()
