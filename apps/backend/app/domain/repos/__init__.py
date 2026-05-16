"""domain/repos — repo allowlist."""

from app.domain.repos import web  # noqa: F401 — registers routes at import time
from app.domain.repos.models import RepoRow
from app.domain.repos.service import (
    Repo,
    RepoNotFoundError,
    add_repo,
    clear_language_hint,
    get,
    get_by_external,
    is_allowed,
    list_repos,
    remove_repo,
    set_language_hint,
)

__all__ = [
    "Repo",
    "RepoNotFoundError",
    "RepoRow",
    "add_repo",
    "clear_language_hint",
    "get",
    "get_by_external",
    "is_allowed",
    "list_repos",
    "remove_repo",
    "set_language_hint",
]
