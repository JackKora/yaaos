# `domain/tickets` (FE) — Internal Architecture

> The ticket list and ticket detail pages. The detail page is the product's signature moment — watching three agents review a PR live.

Lives at `apps/web/src/domain/tickets/index.tsx` (single file, ~1100 LOC: list page + detail page + Teach-yaaof modal).

## Two pages, one route prefix

| Path | Component | Data |
|---|---|---|
| `/tickets` | `TicketsPage` | `useTickets()` → list of tickets enriched server-side with `pr_number`, `author_login`, `is_draft` (from a join on `pull_requests` at read-time). |
| `/tickets/$ticketId` | `TicketDetailPage` | `useTicket(id)` + `useReviewJobsForTicket(id)` + `useTicketAudit(id)` + `useReviewerAgents()`. |

## Tickets list

- **Filter chips** (status): All / Review / Done, each with live counts derived from the currently-loaded list.
- **Filter dropdowns**: `repo` (union of live GitHub-installed repos via `useGithubRepositories()` + distinct `repo_external_id` seen on tickets), `kind` (hardcoded `feature` per [M01-DELTAS § Tickets — kind chip](../../../plan/design/M01-DELTAS.md)), `author` (distinct `author_login` from current tickets).
- **Group-by toggle**: None / Status. Status mode renders sub-tables per status with their own counts.
- **Row layout** (table-style, CSS grid): status badge · `#PR · repo` + title · kind chip · verdict dots (one per agent) · cost · source icon (GitHub) · author avatar+login · tokens · updated-ago.
- **Verdict dots**: lazy per-row, fetch via `useReviewJobsForTicket(id)` (TanStack Query dedupes across rows). Posted-no-findings = green dot; posted-with-must-fix = red; posted-other = grey; running = pulsing accent; queued = grey square; failed = red; absent = empty square.
- **Cost / tokens cells**: sum across all review-jobs for the ticket (same query).

## Ticket detail

- **Header**: `#PR · repo` line, title, status + kind + draft chips, author byline. **Cancel jobs** + **Re-review** buttons.
- **Tabs**: Review (default) / Audit log, with live counts (findings total in Review tab, audit entry count in Audit tab).
- **Review tab — SummaryStrip**: 5 cells side-by-side — Findings (red if any `must-fix`), Total cost, Tokens, Latency (live-ticking when any agent is `running`, else longest job's `duration_s`), Lessons applied.
- **Review tab — three AgentCards** (architecture / security / style), each with a state machine:
  - `no-job` → "no review run yet — click Re-review."
  - `queued` → grey square + "Waiting for an open slot…"
  - `running` → current_step + indeterminate animated bar + live tokens & cost.
  - `posted` → list of findings.
  - `skipped` → "Skipped: `<skip_reason>`."
  - `failed` → "Failed: `<error_message>`."
  - `cancelled` → "Cancelled (`<skip_reason>`)."
- **Finding rows**: severity dot + title + severity label + file:line. Expandable to body, italic rationale, structured snippet diff (line-numbered with `+`/`-`/context coloring), applied-lesson chip linking to `/memory`, **Teach yaaof…** button opening a modal.
- **Teach yaaof modal**: pre-filled title (empty) + body (finding's body, editable, 1000-char cap) + the repo from the ticket. Submit creates a Lesson via `useCreateLesson` → invalidates Memory caches → closes.

## Live updates — SSE wired

A single `EventSource` mounted at the app root (`apps/web/src/main.tsx` → `<SSESubscriber>` from `core/sse`). It subscribes to `/api/events` (no filter — see all events for this org) and translates each event into TanStack-Query cache invalidations:

| Event `kind` | Invalidates |
|---|---|
| `ticket_status_changed` | `["tickets"]`, `["tickets", id]`, `["tickets", id, "audit"]`, `["reviewer", "metrics"]` |
| `review_job_status_changed` | `["reviewer", "jobs", id]`, `["tickets", id, "audit"]`, `["reviewer", "metrics"]`, `["tickets"]` |
| `review_job_step_progress` | `["reviewer", "jobs", id]` only — in-place AgentCard step swap, no metrics / list churn |

Anything subscribed to those keys refetches automatically — pages, summary cells, dashboard metrics, etc. Polling intervals on the same queries (5s / 3s) remain as a safety net for missed SSE messages.

Backwards-compatible with future event kinds: unknown kinds are silently ignored.

## Cancel / Re-review

- **Re-review**: `POST /api/reviewer/rereview` (already existed) — wraps `schedule_review(ticket_id, agent_names="all")`. Cancels any in-flight jobs for the same `(pr_id, agent_id)` pair as part of `schedule_review`'s queue discipline.
- **Cancel jobs**: `POST /api/reviewer/cancel?ticket_id=...` (added 2026-05-16) — wraps `cancel_pending(ticket_id, reason="ui_cancel")`. Flips queued + running rows to `cancelled` with `skip_reason="ui_cancel"`; the running coro's next cancel-check polling point bails out gracefully.

## Why a single file

`apps/web/src/domain/tickets/index.tsx` holds both pages and ~10 inner components (FilterBar, StatusBadge, KindChip, VerdictDots, AgentCard, FindingRow, etc.). The pieces are tightly coupled — they share types, helpers, and visual idiom — and splitting them across files added more import overhead than it saved. If the file grows past ~1500 LOC, split: `list/` and `detail/` subdirectories with shared bits in `_shared.tsx`.
