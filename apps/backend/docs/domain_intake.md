# domain/intake

> Single inbound-signal endpoint. Plugins register `IntakeType` handlers; `POST /api/intake/{type}` verifies, dedups, and either creates a ticket + starts a workflow or applies a side-effect.

## Purpose

The policy layer between external signals (webhooks, etc.) and yaaos state. Owns no tables — coordinates writes across `tickets`, `pull_requests`, `reviewer`, and `core/audit_log` via plugin-supplied handlers.

## Public interface

Exported from `app/domain/intake/__init__.py`:

- `IntakeType` (Protocol) — `name: str`; `handle(*, headers, body, session) -> IntakeOutcome`.
- `IntakePrepared` — ticket-creating outcome (carries `workflow_name` per event).
- `IntakeSideEffect` — non-ticket outcome (handler already mutated state via the endpoint's session; `detail: str` for the response body).
- `IntakeOutcome = IntakePrepared | IntakeSideEffect`.
- `IntakeRejectedError(kind, message)` — `bad_signature` → 401, `bad_request` → 400, `unsupported` → 422.
- `register_intake_type`, `get_intake_type`, `registered_intake_types`.
- `parse_rereview(body)` — pure helper, returns `(matched, agent_name | None)`.
- `is_skippable_path(path)` — pure helper for lockfiles, vendor dirs, generated files, binary extensions. Re-used by `domain/reviewer`.
- `IntakeError` — base exception (uncommon; most handlers prefer audit-and-continue).

HTTP: `POST /api/intake/{type}`. The endpoint reads body + headers, dispatches to the registered handler, branches on the return:

- `IntakePrepared` → `tickets.create(...)` (idempotent on `(org_id, idempotency_key)`); on first create, `engine.start(prepared.workflow_name, ticket_id, session=s)` and attach the execution id to the ticket; all in one transaction.
- `IntakeSideEffect` → just commit the endpoint's session (the handler already wrote what it needed).

## Module architecture

### Files

- `registry.py` — `IntakeType` protocol, `IntakePrepared`, `IntakeSideEffect`, `IntakeRejectedError`, process-local registry.
- `web.py` — `POST /api/intake/{type}` route; reads body, calls handler, branches on outcome.
- `parsing.py` — `parse_yaaos_command`, `parse_rereview`, `is_skippable_path`. Pure, unit-tested.
- `service.py` — `IntakeError` (placeholder).
- `module.py` — `get_module_name() -> "intake"`.

### Registered handlers

- `github` (in `plugins/github.intake_type`) — single entry for every GitHub webhook event. Branches on `X-Github-Event` + `payload.action`. See [plugins_github.md](plugins_github.md).

### Idempotency

Two layers:

- **Delivery-level** — handlers that record raw webhook payloads (the github type writes `github_webhook_events.source_event_id`) dedupe duplicate retries; a second delivery returns `IntakeSideEffect(detail="duplicate")` and the endpoint commits a no-op.
- **Ticket-level** — `IntakePrepared.idempotency_key` is unique on `tickets`. The github type also keys ticket inserts on `(org_id, source, source_external_id)` to catch concurrent deliveries that arrive with different delivery ids.

### Filtering

Filters live inside each `IntakeType`'s `handle()`. The github type drops draft PRs, forks, and bot authors; each drop writes `webhook_event.filtered` with `{reason, event_kind, source_event_id}` so the audit log shows why nothing happened.

### `@yaaos rereview` parser

Single case-insensitive regex in `parsing.py`: `@yaaos(?:-[a-z0-9-]+)?\s+rereview`. Legacy `@yaaos-<specialty>` forms still match for backwards compatibility; the specialty is ignored. Body-parsed token, not a GitHub mention. `parse_yaaos_command` handles the newer `/yaaos full review` / `/yaaos cancel` / `/yaaos review` forms.

### Skip-path heuristics

`is_skippable_path` matches the trivial-diff skip list: lockfiles (`package-lock.json`, `yarn.lock`, `Cargo.lock`, `poetry.lock`, `Pipfile.lock`, `Gemfile.lock`, `go.sum`), vendor dirs (`node_modules/`, `vendor/`, `third_party/`, `dist/`, `build/`, `out/`), generated conventions (`*.pb.go`, `*.gen.*`, `_generated` substring), and binary extensions. `domain/reviewer` re-imports this so intake stays the single source of truth.

### Audit-log entries written by handlers

| Kind | When | Payload |
|---|---|---|
| `webhook_event.filtered` | A filter rule rejects an event | `{reason, event_kind, source_event_id}` |
| `ticket.created` | First-time PR upsert creates the ticket | `{pr_id, repo_external_id}` |
| `ticket.rereview_requested` | `/yaaos …` or `@yaaos rereview` matched | `{comment_external_id}` |
| `ticket.reaction_received` | Reaction added to a yaaos comment | `{reaction, target_comment_external_id}` |

`webhook_event.filtered` uses a synthetic UUID as entity id (no webhook row id at the handler layer).

### Error handling

Per-event isolation lives inside each handler. The endpoint surfaces `IntakeRejectedError` as the matching HTTP status; uncaught exceptions roll back the endpoint's session and return 500. Missed events recover via the plugin's catch-up poller (where one exists).

## Data owned

None. Writes through `tickets`, `pull_requests`, `reviewer`, and `core/audit_log`.

## How it's tested

`app/domain/intake/test/test_parsing.py` covers `parse_rereview`, `parse_yaaos_command`, and `is_skippable_path` exhaustively. `app/domain/intake/test/test_intake_endpoint.py` drives `POST /api/intake/{type}` end-to-end against a stub `IntakeType`: happy path (ticket + workflow + outbox row), unknown type (404), bad signature (401), duplicate idempotency_key. Per-plugin handler logic is tested under each plugin (e.g., `apps/backend/app/plugins/github/test/`).
