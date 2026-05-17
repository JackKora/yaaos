"""Default seeded PRs and diffs used by e2e tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def default_seeded_prs() -> dict[str, dict[str, Any]]:
    """Two PRs across two repos. PR keys are `owner/repo#number`."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "acme/web#1": _pr("acme/web", 1, "Refactor user list", "Cleaner API for the user list.", now),
        "acme/api#1": _pr("acme/api", 1, "Add /metrics endpoint", "Expose Prometheus metrics.", now),
    }


def _pr(repo: str, number: int, title: str, body: str, now: str) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    return {
        "number": number,
        "title": title,
        "body": body,
        "draft": False,
        "merged": False,
        "state": "open",
        "html_url": f"https://github.com/{repo}/pull/{number}",
        "user": {"login": "alice", "type": "User"},
        "head": {"ref": "feat", "sha": f"head-sha-{repo.replace('/', '-')}-{number}", "repo": {"fork": False}},
        "base": {"ref": "main", "sha": f"base-sha-{repo.replace('/', '-')}-{number}"},
        "created_at": now,
        "updated_at": now,
        "_repo": {"full_name": repo, "owner": {"login": owner}, "name": name},
    }


def default_seeded_diffs() -> dict[str, str]:
    return {
        "acme/web#1": _sample_diff_web(),
        "acme/api#1": _sample_diff_api(),
    }


def default_installation_repositories() -> list[dict[str, Any]]:
    """Repos the seeded App-install can see — drives yaaos's catch-up poller
    and the Settings GitHub-card live repo list."""
    return [
        {"full_name": "acme/web", "html_url": "https://github.com/acme/web", "private": False},
        {"full_name": "acme/api", "html_url": "https://github.com/acme/api", "private": False},
    ]


def default_seeded_files() -> dict[str, list[dict[str, Any]]]:
    return {
        "acme/web#1": [
            {"filename": "src/user/list.ts", "status": "modified", "additions": 12, "deletions": 4},
        ],
        "acme/api#1": [
            {"filename": "app/metrics.py", "status": "added", "additions": 28, "deletions": 0},
        ],
    }


def _sample_diff_web() -> str:
    return """diff --git a/src/user/list.ts b/src/user/list.ts
@@
-export function getUsers() { return fetch('/api/users').then(r => r.json()) }
+export async function getUsers() {
+  const r = await fetch('/api/users');
+  if (!r.ok) throw new Error('failed');
+  return r.json();
+}
"""


def _sample_diff_api() -> str:
    return """diff --git a/app/metrics.py b/app/metrics.py
new file mode 100644
@@
+from fastapi import APIRouter
+
+router = APIRouter()
+
+@router.get('/metrics')
+def metrics():
+    return {'ok': True}
"""
