# core/routing

> TanStack Router config — URL → component mapping for the SPA.

## Purpose

Every authenticated page lives under `/orgs/$slug/...`. There is exactly one URL tree for authenticated work; the only routes that render outside it are `/login` and `/orgs` (the picker). User-account pages (`Details`, `Security`, `Notifications`) sit at `/orgs/$slug/user/*` — the slug is always part of the URL, which is the only source of truth for current org context.

## Public interface

- `router` — TanStack `Router` instance, consumed by `main.tsx`'s `<RouterProvider>`.

The module declares the TanStack `Register` augmentation so `<Link to="/orgs/$slug/...">` gets typed autocomplete.

## Module architecture

### Route tree

| Path | Component | Notes |
|---|---|---|
| `/` | beforeLoad probe | Hits `/api/auth/me`. 401 → `/login`. 200 + 1 membership → that org's dashboard. 200 + 0 or >1 → `/orgs` picker. |
| `/login` | `LoginPage` (`@domain/auth`) | `beforeLoad` probes `/api/auth/me`; on 200, redirects to `/` (prevents authed-user bounce loop). Reads `?reason=` (`signed_out`, `expired`, `idle`, `not_provisioned`) for the banner. |
| `/orgs` | `OrgPickerPage` | Standalone (no sidebar). Empty state when the user has zero memberships ("ask an admin to invite you"). |
| `/orgs/$slug` | scope-only route | Parent for all org-scoped subtrees, including user-area pages. |
| `/orgs/$slug/dashboard` | `DashboardPage` | |
| `/orgs/$slug/tickets`, `…/$ticketId` | `TicketsPage`, `TicketDetailPage` | |
| `/orgs/$slug/lessons` | `LessonsPage` | |
| `/orgs/$slug/settings` | redirect | 303 → `/orgs/$slug/settings/auth`. |
| `/orgs/$slug/settings/{auth,members,audit,vcs,coding-agents,coding-agents/$pluginId,api-keys,mcp-proxy,workspace}` | per-page `…SettingsPage` | Owner/Admin gates per page. |
| `/orgs/$slug/user` | redirect | 303 → `…/user/details`. |
| `/orgs/$slug/user/{details,security,notifications}` | `DetailsPage`, `SecurityPage`, `NotificationsPage` | USER_SCOPED on the backend (`/api/user/*`, `/api/notifications/*`); the slug in the path is purely a frontend routing concern. |

### Slug source of truth = URL

`apps/web/src/core/api/org-context.ts` exposes `getCurrentOrgSlug()` (plain function) and `useCurrentOrgSlug()` (React hook). Both derive the slug from the URL on every read — there is no module-global cache, no localStorage, no server-stored "current org" field. Two browser tabs in different orgs stay independent because each tab reads its own `window.location`.

`apiFetch` reads the slug from `getCurrentOrgSlug()` to attach `X-Org-Slug` (backend USER_SCOPED + PUBLIC routes ignore the header anyway). Chrome components (sidebar, switcher, banner, user-card, notifications-bell) read `useCurrentOrgSlug()` so they re-render on SPA navigation.

The chrome only renders inside the org-scope route (the `STANDALONE_PATHS` exit early for `/login` and `/orgs`), which means every chrome component is guaranteed to see a non-null slug. Bare-href fallbacks like `/dashboard` are gone — the entire premise was a slug that might be null in the chrome, and that can no longer happen.

### `/api/auth/me` contract

Returns `{user, memberships[]}`. `memberships` are the authenticated user's current memberships (each entry: `slug`, `display_name`, `role`, `handle`, `broken_integrations`). Revoked memberships disappear on the next call. There is no `current_org_slug` field — the server has no opinion about which org you're "in"; that's view state and lives in the URL.

### Login + provisioning

- Anonymous user hits any URL → central 401 handler hard-navigates to `/login?reason=signed_out&next=…`.
- `LoginPage` enumerates `/api/auth/providers`; clicking a button hits `/api/auth/login?provider=<id>&next=<path>`.
- OAuth callback completes server-side. The server matches `(provider, external_subject)` first, then verified-email; if neither matches, it redirects to `/login?reason=not_provisioned` with NO cookie set — **OAuth never auto-provisions**. New users must be invited (see `/api/memberships/accept`).
- On success, the server applies `_safe_next` plus membership validation: if `next` points at `/orgs/$slug/...`, the resolved user must have a membership in `$slug`; otherwise the redirect collapses to `/`.
- `/` probe routes per the rules above.

### In-app navigation discipline

- All in-SPA navigation uses `<Link>` from `@tanstack/react-router`. Native `<a href="/internal/path">` triggers a full browser reload and is reserved for external URLs (`target="_blank" rel="noopener noreferrer"`) and backend full-redirect routes under `/api/`.
- Grep guard: `grep -rn '<a\s[^>]*href="/' apps/web/src` must return no in-SPA hits.

### Type augmentation

`router.tsx` declares `module "@tanstack/react-router"` augmenting `Register` so `<Link to="/orgs/$slug/tickets/$ticketId">` type-checks everywhere. Pass interpolated strings (`<Link to={`/orgs/${slug}/dashboard`}>`) only when forced; prefer the pattern + `params={{ slug }}` form for full type safety.

## Data owned

None. The slug is derived from the URL on every read.

## How it's tested

- `apps/e2e/tests/login-and-membership.spec.ts` covers the full login → org-scoped routes → membership flow via the `oauth_test` provider, including the regression case (hard-nav to `/orgs/acme/user/details` then click Dashboard).
- `apps/e2e/tests/session-died-redirect.spec.ts` covers 401 → `/login?reason=…&next=…` round trips.
- Backend `apps/backend/app/domain/sessions/test/test_oauth_endpoints.py` covers no-auto-provisioning and the not-provisioned redirect.
