# core/sse

> Single `EventSource` mounted at app root; translates server events into TanStack Query cache invalidations.

## Purpose

yaaos's UI is driven by a server-side event stream — the reviewer pipeline emits `ticket_status_changed`, `review_job_status_changed`, and `review_job_step_progress` at every state transition. This module owns the single browser-wide `EventSource` and maps event kinds to cache invalidations. Domain modules consume queries; `core/sse` makes those queries refresh.

## Public interface

- `<SSESubscriber>` — React component mounted once in `main.tsx` between `QueryClientProvider` and `RouterProvider`. Renders `children` through; the work is a side effect inside a `useEffect`.
- `ServerEvent` — envelope type: `{ kind, source_module, ts, ticket_id, [extra]: unknown }`.

## Module architecture

### Mounting

`<SSESubscriber>` wraps the router in `main.tsx`. One `EventSource("/api/events")` per mount → one per browser tab. The effect's cleanup closes it on unmount.

### Event → invalidation map

| Event `kind` | Invalidates |
|---|---|
| `ticket_status_changed` | `["tickets"]`, `["tickets", id]`, `["tickets", id, "audit"]`, `["reviewer", "metrics"]` |
| `review_job_status_changed` | `["reviewer", "jobs", id]`, `["tickets", id, "audit"]`, `["reviewer", "metrics"]`, `["tickets"]` |
| `review_job_step_progress` | `["reviewer", "jobs", id]` only — in-place AgentCard step swap, no metrics/list churn |
| anything else | silently ignored |

`ticket_id` on the envelope scopes invalidations. Events without it fall back to the global keys (`["tickets"]`, `["reviewer", "metrics"]`).

### Reconnection

Native `EventSource` auto-reconnects on socket drop with exponential backoff. `onerror` is a logger; the browser handles retry. The safety-net 3-5s polling on the underlying queries covers any state drift during a long disconnect.

### Why a subscriber, not per-component listeners

Each `EventSource` is a long-lived stream holding a server-side connection. Mounting one per component would multiply connections by N pages × M tabs. One-at-the-root keeps it at exactly 1 per tab and centralises the invalidation map.

### SSR safety

The effect early-returns if `window` or `EventSource` is undefined. Browser-only today; the guard means a future SSR pass won't crash.

## Data owned

None. The `EventSource` is per-mount.

## How it's tested

End-to-end via `apps/e2e/tests/sse-step-progress-live.spec.ts` — dispatches a webhook, opens the ticket detail page without refreshing, asserts the review card transitions to `posted` via SSE-driven invalidations alone. No Vitest — mocking `EventSource` would test the mock more than the code.
