# domain/tickets

> Ticket list and ticket detail — the product's signature surface where three agents post live reviews.

## Purpose

Two pages under `/tickets`:
- `/tickets` — filterable, group-able list of every ticket.
- `/tickets/$ticketId` — detail: per-agent cards (architecture / security / style), expandable findings, audit log, Teach-yaaos modal.

The only surface that exercises the full live-update path (webhook → reviewer pipeline → SSE → AgentCard state swap).

## Public interface

- `TicketsPage`, `TicketDetailPage` — mounted by `core/routing` at `/tickets` and `/tickets/$ticketId`. The Teach-yaaos modal is a private subcomponent.

## Module architecture

`apps/web/src/domain/tickets/index.tsx` is a single ~1100-LOC file holding both pages plus ~10 inner components. Pieces are tightly coupled (shared types/helpers/idiom). Split into `list/` + `detail/` + `_shared.tsx` when the file passes ~1500 LOC.

### List page

`TicketsPage`:
- **Filter chips (status)** — All / Review / Done with live counts from `useTickets()`.
- **Filter dropdowns** — `repo` (union of `useGithubRepositories()` and distinct `repo_external_id`s on loaded tickets), `kind` (hardcoded to `feature` — no `kind` field on Ticket yet), `author` (distinct `author_login`s).
- **Group-by toggle** — None / Status. Status mode renders sub-tables per status.
- **Row layout (CSS grid)** — status badge · `#PR · repo` + title · kind chip · verdict dots (one per agent) · cost · source icon · author avatar+login · tokens · updated-ago.
- **Verdict dots** — lazy per-row via `useReviewJobsForTicket(id)` (TanStack Query dedupes). Colors: posted-no-findings green, posted-with-must-fix red, posted-other grey, running pulsing accent, queued grey square, failed red, absent empty.
- **Cost / tokens cells** — summed across the ticket's review jobs.

### Detail page

`TicketDetailPage`:
- **Header** — `#PR · repo`, title, status + kind + draft chips, author byline. Buttons: **Cancel jobs** and **Re-review**.
- **Tabs** — Review (default) and Audit log, each with live counts. Test IDs `tab-review` / `tab-audit`.

### Review tab — `SummaryStrip`

Five-cell card: Findings (red if any must-fix), Total cost, Tokens (in + out), Latency (live-ticking `LiveLatency` re-renders every second while any agent is `running`; otherwise the longest completed job's `duration_s`), Lessons applied (count of unique `lessons_applied` UUIDs across jobs).

### Review tab — three `AgentCard`s

One per built-in agent. Each carries `data-testid="agent-card-${name}"` and `data-state="<status>"` so e2e can query `[data-testid^="agent-card-"][data-state="posted"]`.

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

Inside `findings-list`: severity dot + title + severity label + `file:line`. Click expands → body, italic `rationale`, line-numbered snippet diff with +/-/context coloring. Applied-lesson chip(s) link to `/memory`. **"Teach yaaos…"** button (`data-testid="teach-yaaos"`) opens the modal.

### Teach-yaaos modal

Pre-fills title (empty), body (finding's body, editable, 1000-char cap), repo (the ticket's). Submit → `useCreateLesson` posts `/api/memory/lessons`, invalidates `["memory", repo]`, closes. Uses the shared `Dialog` primitives.

### Audit tab

Renders `useTicketAudit(id)` as a vertical list: `formatTime(created_at)` · `kind` · `[actor.kind:actor.login]`. Click expands the full payload JSON. Timestamps go through `formatTime` for local TZ.

### Cancel / Re-review

- **Re-review** — `useRereviewMutation` → `POST /api/reviewer/rereview?ticket_id=...`. Cancels in-flight jobs for `(pr_id, agent_id)` pairs via supersede discipline, then schedules a fresh batch.
- **Cancel jobs** — `useCancelReviewerJobs` → `POST /api/reviewer/cancel?ticket_id=...`. Flips queued + running to `cancelled` with `skip_reason="ui_cancel"`; running coros bail at their next cancel-check.

### Live updates

The SSE subscriber invalidates `["tickets"]`, `["tickets", id]`, `["tickets", id, "audit"]`, `["reviewer", "jobs", id]`, and `["reviewer", "metrics"]` on the appropriate kinds (see [core_sse.md](core_sse.md)). 3s polling is the safety net.

## Data owned

None. State lives in `core/api` caches; mutations target endpoints owned by `domain/reviewer` and `domain/memory`.

## How it's tested

E2e specs in `apps/e2e/tests/`:
- `pr-review-end-to-end.spec.ts` — webhook → 3 agents post → findings render.
- `pr-resync-reruns-agents.spec.ts` — synchronize event triggers a fresh batch.
- `manual-rereview-and-cancel.spec.ts` — re-review through UI; cancel through API.
- `secrets-refuse-to-review.spec.ts` — all 3 transition to `skipped(secrets_detected)`.
- `teach-yaaos-from-finding.spec.ts` — finding → modal → lesson on Memory page.
- `lesson-applied-next-review.spec.ts` — seeded lesson surfaces in `prompt_sent` audit payload.
- `sse-step-progress-live.spec.ts` — AgentCard transitions to `posted` without reload.

No Vitest — components are render-heavy and the e2e specs cover the round-trip.
