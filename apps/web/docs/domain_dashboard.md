# domain/dashboard

> Landing page for an org session — stat cards, agent row, in-flight band, needs-attention band.

## Scope

`/orgs/:slug/dashboard`. Queries: `useDashboard()` → `GET /api/tickets/dashboard`; `useAgents(slug)` → `GET /api/orgs/{slug}/agents`. `NotConfiguredBanner` reads `GET /api/orgs/config-status` separately. Owns no data.

## Layout

- **4 stat cards** — In flight (spins when > 0) · HITL pending · Completed today · Failed today.
- **Workspace agents row** — one `AgentCard` per agent within the 1-hour retention window. Empty-state card links to `/settings/workspaces` when no agents are connected. Visible to all org members.
- **In flight band** — up to 10 running tickets (title, repo, age). Click → detail.
- **Needs attention band** — up to 5 done tickets with ≥1 medium/high finding. Click → detail.
- **`NotConfiguredBanner`** — mounts above cards when `configured: false`. Admins see missing-piece list; Builders see "Ask [admin] to finish setup." Bands still render so historical tickets remain visible.

## `AgentCard`

`AgentCard.tsx` — richer card per agent. Shows `instance_id` (display name), liveness state badge (reachable → green, stale → amber, offline → muted), OS/CPU/memory metadata, workspace count, and a client-ticking relative last-seen label (no refetch — updates via `setInterval` every 5 s). Liveness state transitions come from SSE invalidations, not polling.

## Live updates

Pure SSE — no polling. `agent_liveness_changed` events invalidate `["agents"]`; `ticket_status_changed`, `review_*`, and `finding_*` events invalidate `["tickets"]` and `["tickets", "dashboard"]`. On every `(re)connect`, `onopen` reconciles by invalidating `["agents"]` and list-level ticket keys.

## Tests

`test/dashboard.test.tsx` — loading skeleton smoke test. Populated state covered by PR-review e2e. Agent cards live behavior covered by the dashboard-agents e2e spec.
