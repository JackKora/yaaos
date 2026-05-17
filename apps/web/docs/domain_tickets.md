# domain/tickets

> Ticket list and ticket detail — the product's signature surface where the yaaos parent reviewer posts live reviews.

## Purpose

Two pages under `/tickets`:
- `/tickets` — filterable, group-able list of every ticket.
- `/tickets/$ticketId` — detail: one review card showing findings tagged by the subagent that surfaced each, audit log, Teach-yaaos modal.

The only surface that exercises the full live-update path (webhook → reviewer pipeline → SSE → review card state swap).

## Public interface

- `TicketsPage`, `TicketDetailPage` — mounted by `core/routing` at `/tickets` and `/tickets/$ticketId`. The Teach-yaaos modal is a private subcomponent.

## Module architecture

`apps/web/src/domain/tickets/index.tsx` is a single file holding both pages plus inner components. Pieces are tightly coupled (shared types/helpers/idiom). Split into `list/` + `detail/` + `_shared.tsx` when the file passes ~1500 LOC.

### List page

`TicketsPage`:
- **Filter chips (status)** — All / Review / Done with live counts from `useTickets()`.
- **Filter dropdowns** — `repo`, `kind` (hardcoded to `feature`), `author`.
- **Group-by toggle** — None / Status. Status mode renders sub-tables per status.
- **Row layout (CSS grid)** — status badge · `#PR · repo` + title · kind chip · verdict dot · cost · source icon · author avatar+login · tokens · updated-ago.
- **Verdict dot** — lazy per-row via `useReviewJobsForTicket(id)`. Colors: posted-no-findings green, posted-with-must-fix red, posted-other grey, running pulsing accent, queued grey square, failed red, absent empty.
- **Cost / tokens cells** — read from the latest review job.

### Detail page

`TicketDetailPage`:
- **Header** — `#PR · repo`, title, status + kind + draft chips, author byline. Buttons: **Cancel jobs** and **Re-review**.
- **Tabs** — Review (default) and Audit log, each with live counts.

### Review tab — `SummaryStrip`

Five-cell card: Findings (red if any must-fix), Total cost, Tokens, Latency (live-ticking `LiveLatency` while running; otherwise `duration_s`), Lessons applied.

### Review tab — `AgentCard`

One card representing the yaaos parent reviewer. Carries `data-testid="agent-card-yaaos"` and `data-state="<status>"`.

| Status | Body |
|---|---|
| `no-job` | "no review run yet — click Re-review." |
| `queued` | grey square + "Waiting for an open slot…" |
| `running` | `current_step` label + indeterminate bar + live tokens & cost |
| `posted` | list of `Finding` rows |
| `skipped` | `Skipped: <skip_reason>.` |
| `failed` | `Failed: <error_message>.` |
| `cancelled` | `Cancelled (<skip_reason>).` |

### Finding rows

Inside `findings-list`: severity dot + title + severity label + `file:line` + subagent tag from `source_agent`. Click expands → body, italic `rationale`, line-numbered snippet diff. Applied-lesson chip(s) link to `/memory`. **"Teach yaaos…"** button opens the modal.

### Teach-yaaos modal

Pre-fills title (empty), body (finding's body, editable, 1000-char cap), repo (the ticket's). Submit → `useCreateLesson` posts `/api/memory/lessons`, invalidates `["memory", repo]`, closes.

### Audit tab

Renders `useTicketAudit(id)` as a vertical list: `formatTime(created_at)` · `kind` · `[actor.kind:actor.login]`. Click expands the full payload JSON.

### Cancel / Re-review

- **Re-review** — `useRereviewMutation` → `POST /api/reviewer/rereview`. Cancels in-flight jobs for the PR via supersede discipline, then schedules one new review.
- **Cancel jobs** — `useCancelReviewerJobs` → `POST /api/reviewer/cancel?ticket_id=...`.

### Live updates

The SSE subscriber invalidates `["tickets"]`, `["tickets", id]`, `["tickets", id, "audit"]`, `["reviewer", "jobs", id]`, and `["reviewer", "metrics"]` on the appropriate kinds (see [core_sse.md](core_sse.md)). 3s polling is the safety net.

## Data owned

None. State lives in `core/api` caches; mutations target endpoints owned by `domain/reviewer` and `domain/memory`.

## How it's tested

E2e specs in `apps/e2e/tests/` exercise the round-trip; assertions check for exactly one `agent-card-` per ticket. No Vitest — components are render-heavy.
