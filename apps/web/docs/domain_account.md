# domain_account

> User-scoped settings: profile, per-org handles, GitHub link, 2FA, sessions, messaging placeholder.

## Surfaces

- `/user/details` — `DetailsPage`. Display name, per-org handles table, verified emails list, GitHub association.
- `/user/security` — `SecurityPage`. TOTP enrollment + sign-out-all-sessions.
- `/user/messaging` — `MessagingPage`. Placeholder (empty-state only) — Slack / email integration is post-M06.

## Data flow

- `useAccountMe` → `GET /api/account/me`. Source of truth for the page; carries display name, emails, github_username, and the user's org memberships with their handles.
- Display name + handle edits go through `useUpdateDisplayName` / `useUpdateOrgHandle` (PATCH); GitHub clear goes through `useClearGithubUsername`.
- TOTP enroll + verify mutations talk to `/api/auth/totp/{enroll,verify}` directly via `apiFetch` (state is local to the page; no shared cache).
- `useLogoutAll` lives in `domain_auth`; SecurityPage imports it.

## State / contract

- Display name input is dirty-state aware (`Save` disabled until value differs).
- Per-org handle save reports its own error inline — table row stays editable while other rows reset cleanly.
- TOTP enroll → show seed + otpauth URI → verify with 6-digit code → page reflects `verified` badge (in-memory only; reload re-derives from `/api/auth/me`).

## Where the code lives

- `apps/web/src/domain/account/{DetailsPage,SecurityPage,MessagingPage}.tsx`
- Vitest smoke tests in `apps/web/src/domain/account/test/`.
