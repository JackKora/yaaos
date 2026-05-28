# core/api

> Typed HTTP client + the full TanStack Query hook surface every domain module consumes.

## Purpose

A small, hand-maintained layer between the FastAPI backend and the UI. Owns the typed `openapi-fetch` client, a generic `apiFetch<T>` helper, TypeScript shapes for every API resource, and one TanStack Query hook per endpoint.

## Public interface

Re-exports from `@core/api`:
- **Client:** `apiClient`, `apiFetch`, `getCurrentOrgSlug`, `setCurrentOrgSlug`.
- **Resource types:** `HealthResponse`, `Ticket`, `Lesson`, `ReviewJob`, `ReviewJobActivityEvent`, `Finding`, `FindingSnippetLine`, `AuditEntry`, `GithubInstallation`, `GithubRepository`, `GithubRepositoriesResponse`, `PluginMeta`, `PluginType`, `PluginHealth`, `ConfigStatus`, `CreateOrgResponse`, `DashboardResponse`, `DashboardStats`, `HitlHistoryEntry`, `MineOrg`, `Notification`, `NotificationsPopover`, `SsoDiscoverResult`, `ConversationRow`, `FindingRow`, `FindingThread`, `OrgSettings`, `ReviewTimelineRow`, `ThreadMessage`, `WorkspaceConnectionStatus`.
- **Queries:** `useHealth`, `useConfigStatus`, `useDashboard`, `useTickets`, `useTicket`, `useTicketAudit`, `useReviewsForTicket`, `useReviewJobsForTicket`, `useLessons`, `useMetricsSummary`, `useGithubInstallation`, `useGithubRepositories`, `usePluginHealth`, `useNotifications`, `useNotificationsPopover`, `useMyOrgs`, `useHitlHistory`, `useOrgSettings`, `useWorkspaceConnectionStatus`, `useConversationsForTicket`, `useFindingsForTicket`, `useThreadForFinding`.
- **Mutations:** `useRereviewMutation`, `useFullRereviewMutation`, `useCancelReviewerJobs`, `useCreateLesson`, `useDeleteLesson`, `useSetAnthropicKey`, `useMarkNotificationRead`, `useMarkAllNotificationsRead`, `useAckFinding`, `usePushBackFinding`, `useCreateOrg`, `useHitlRespond`, `useSsoDiscover`, `useUpdateOrgSettings`.

## Module architecture

### Two clients, one helper

`client.ts`:
- `apiClient` — `openapi-fetch` typed client. `Paths` is hand-declared and currently only covers `/api/health`.
- `apiFetch<T>(path, init?)` — generic fetch wrapper. On `401` it hands the response to [`handleAuthFailure`](../src/core/api/auth-failure.ts) (lazy-imported to break the load-path cycle), which hard-navigates to `/login?reason=...&next=<current-path>` and throws `AuthError`. On any other non-2xx, throws `${status} ${path}: ${body}`. Returns `undefined` on 204; parsed JSON otherwise.

OpenAPI codegen is deferred — the surface is small enough that hand-declared types are cheaper.

### Central 401 handler

`auth-failure.ts` owns the one-and-only redirect-on-auth-died path:

- **Mutex** — a module-level `redirectInProgress` flag means concurrent 401s (every page often fires `/api/auth/me` + `/api/orgs/mine` + page queries in parallel) trigger exactly one `window.location.assign`. Hard nav rather than TanStack Router soft-nav clears React state + the query cache, which is the right thing when the session is dead.
- **Reason mapping** — backend `{"error": "<code>"}` body → UX banner reason: `session_idle_expired → "idle"`, `session_expired → "expired"`, `unauthenticated → "signed_out"`, unknown → `"signed_out"` (catch-all so renames don't break the banner).
- **`next` round-trip** — captures `window.location.pathname + search + hash` and tags it as `?next=`. `LoginPage` forwards it through the OAuth flow's `next` query param; backend `_safe_next` (and our mirroring `safeNext` helper) reject scheme-relative / off-origin paths and `/login` loops. The user lands back where they were trying to go after sign-in. Covers both "session died mid-flow" and "cold deeplink while logged out" identically.
- The backend already clears `yaaos_session` + `yaaos_csrf` via `Set-Cookie: Max-Age=0` on every 401 it issues (see [`apps/backend/app/core/auth/auth_failure.py`](../../backend/app/core/auth/auth_failure.py)), so by the time the redirect fires the browser already has fresh state.

### Resource types

Each API resource has a type alias in `client.ts`, mirroring the backend Pydantic models. Notes:
- `Ticket` — includes `pr_number` / `author_login` / `is_draft` enriched from the linked PR at read-time.
- `Finding` — `severity` is `"must-fix" | "nit" | "suggestion" | "info"`; carries optional `rationale`, `snippet: FindingSnippetLine[]`, `applied_lesson_ids`, and `source_agent` (which yaaos subagent surfaced this finding).
- `ReviewJob` — one row per (PR × review run). Full state including `current_step`, `last_heartbeat_at`, `tokens_in`/`out`, `findings`, `model`, `effort`, and `activity_log` (persisted chronological events from the coding-agent stream).
- `ReviewJobActivityEvent` — `{ts, kind, message, detail?}`. `message` is rendered server-side. Used in `ReviewJob.activity_log` (persisted) and as the payload of workspace-activity SSE events (`/api/sse/workspace_activity/{id}`).
- `PluginMeta` — driven by `/api/settings/plugins` so the Settings UI auto-lists plugins.

### Query hooks

`queries.ts` defines one hook per endpoint:

| Hook | Endpoint | Refetch |
|---|---|---|
| `useHealth` | `GET /api/health` | 5s |
| `useOnboarding` | `GET /api/settings/onboarding` | 5s |
| `useTickets` | `GET /api/tickets` | 3s |
| `useTicket(id)` | `GET /api/tickets/${id}` | — |
| `useTicketAudit(id)` | `GET /api/tickets/${id}/audit` | 3s |
| `useReviewJobsForTicket(id)` | `GET /api/reviewer/jobs/by-ticket/${id}` | 3s |
| `useLessons(repo?)` | `GET /api/lessons[?repo=...]` | — |
| `useMetricsSummary` | `GET /api/reviewer/metrics` | 5s |
| `useGithubInstallation` | `GET /api/github/installation` | 5s |
| `useGithubRepositories` | `GET /api/github/repositories` | on demand |
| `usePluginsList` | `GET /api/settings/plugins` | — |
| `usePluginHealth(id)` | `GET /api/${id}/health` | 5s |

Polling intervals are a safety net for missed SSE messages (see [core_sse.md](core_sse.md)).

### Mutation hooks

Mutations invalidate the keys they affect on success:

| Hook | Endpoint | Invalidates |
|---|---|---|
| `useRereviewMutation` | `POST /api/reviewer/rereview?ticket_id=...` | `["tickets"]`, `["reviewer","jobs",id]`, `["tickets",id,"audit"]`, `["reviewer","metrics"]` |
| `useCancelReviewerJobs` | `POST /api/reviewer/cancel?ticket_id=...` | same as re-review |
| `useCreateLesson` | `POST /api/lessons` | `["lessons", repo]` |
| `useDeleteLesson` | `DELETE /api/lessons/${id}` | `["lessons", repo]` |
| `useSetAnthropicKey` | `POST /api/claude_code/api_key` | `["onboarding"]`, `["plugin-health","claude_code"]` |

Key taxonomy: see [patterns.md § Query keys](patterns.md#query-keys).

## Data owned

None. The `QueryClient` lives in `main.tsx`; hooks here just read/write it.

## How it's tested

- `apps/web/src/domain/dashboard/test/dashboard.test.tsx` exercises `useOnboarding` indirectly.
- Every e2e spec in `apps/e2e/tests/*.spec.ts` drives full hook + backend round-trips.

Non-trivial cache logic (custom `select`, optimistic updates) earns dedicated Vitest tests in `apps/web/src/core/api/test/`.
