# domain/memory

> Per-repo lessons — human-supplied guidance injected into every future review prompt on the repo.

## Purpose

Owns the `lessons` table, CRUD exposed to the UI, the retrieval API used by `reviewer` during prompt assembly, and audit-log writes on every mutation. Small module — complexity in *how* lessons are used during prompt assembly lives in `reviewer`.

## Public interface

Exported from `app/domain/memory/__init__.py`:

- Types — `Lesson`, `LessonRow`.
- Operations — `create`, `list_for_repo`, `list_all`, `get`, `update`, `delete`.
- Exceptions — `LessonNotFoundError`, `LessonValidationError`.

HTTP routes (`/api/memory`):

- `GET /api/memory?repo_external_id=…` — list (filtered by repo if param given; otherwise all in org).
- `POST /api/memory` — create.
- `PUT /api/memory/{lesson_id}` — update title/body/source_pr_url.
- `DELETE /api/memory/{lesson_id}` — hard delete.

All routes use `Actor.system()` and the fixed org id (`00000000-0000-0000-0000-000000000001`).

## Module architecture

### Identity

Lessons are scoped by `(plugin_id, repo_external_id)`. No yaaos-side `repos` table; the GitHub App install picks access scope. `plugin_id` defaults to `"github"` at row and API level.

### `Lesson` model

Pydantic view of the row. `Lesson.from_row(row)` converts a `LessonRow`. Schema in `app/domain/memory/models.py`.

### Validation

`_validate(title, body)` runs on create and update: `title` non-blank ≤200 chars; `body` non-blank ≤1000 chars. Violations raise `LessonValidationError` (HTTP 400).

### Mutations and audit

Every mutation writes through `core.audit_log.audit_for_lesson`:

- `create` → `lesson.created` with `{title, body_length}`.
- `update` → `lesson.updated` with `{fields_changed, prior_body_hash, new_body_hash}` — only when a field actually changed. Hashes are 16-char SHA-256 prefixes.
- `delete` → `lesson.deleted` with `{title, body_hash_at_deletion}`.

Edits overwrite in place — no versioning table; history lives in `audit_log`. Deletes are hard; `lessons` is not FK'd from elsewhere.

### Retrieval semantics

`reviewer` calls `list_for_repo` during prompt assembly and includes every returned lesson. No per-lesson relevance filter, no scope-limiting, no per-agent subsetting. `list_all(org_id)` powers the unfiltered memory-management page. Newest-first by `created_at`. No pagination — at most a few dozen lessons per repo in practice.

### What memory doesn't do

- Doesn't publish events; the page re-queries after each mutation.
- Doesn't snapshot lesson content at review time — `review_jobs.lessons_applied` (owned by `reviewer`) records UUIDs for UI chip resolution; content at that moment is not frozen.
- Doesn't accept lesson creation from PR comments.
- Doesn't deduplicate.

## Data owned

- `lessons` — `(id, org_id, plugin_id, repo_external_id, title, body, source_pr_url, created_at, updated_at)`. Indexed on `(org_id)` and `(org_id, plugin_id, repo_external_id)`.

## How it's tested

`app/domain/memory/test/test_validation.py` — empty title/body rejected, length caps enforced, valid input passes. CRUD + audit covered by HTTP-layer integration tests and by `reviewer`'s tests exercising `list_for_repo`.
