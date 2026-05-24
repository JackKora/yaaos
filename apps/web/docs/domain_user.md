# domain_user

> User-scoped settings: profile, per-org handles, GitHub link, 2FA, sessions, messaging placeholder.

## Surfaces

- `/orgs/$slug/user/details` — `DetailsPage`. Display name, per-org handles table, verified emails list, GitHub association.
- `/orgs/$slug/user/security` — `SecurityPage`. TOTP enrollment + sign-out-all-sessions.
- `/orgs/$slug/user/notifications` — cross-org notifications.

User pages are nested under the current org slug so the URL alone carries all routing context. The backend routes they call (`/api/user/*`, `/api/notifications/*`, `/api/auth/totp/*`) are `USER_SCOPED` and ignore `X-Org-Slug` — the slug in the path is purely a frontend routing concern.

## Data flow

- `useUserMe` → `GET /api/user/me`. Source of truth for the page; carries display name, emails, github_username, and the user's memberships with their handles.
- Display name + handle edits go through `useUpdateDisplayName` / `useUpdateOrgHandle` (PATCH); GitHub clear goes through `useClearGithubUsername`.
- TOTP enroll + verify mutations talk to `/api/auth/totp/{enroll,verify}` directly via `apiFetch` (state is local to the page; no shared cache).
- `useLogoutAll` lives in `domain_auth`; SecurityPage imports it.

## State / contract

- Display name input is dirty-state aware (`Save` disabled until value differs).
- Per-org handle save reports its own error inline — table row stays editable while other rows reset cleanly.
- TOTP enroll → show seed + otpauth URI → verify with 6-digit code → page reflects `verified` badge (in-memory only; reload re-derives from `/api/auth/me`).

## Where the code lives

- `apps/web/src/domain/user/{DetailsPage,SecurityPage,MessagingPage}.tsx`
- Vitest smoke tests in `apps/web/src/domain/user/test/`.
