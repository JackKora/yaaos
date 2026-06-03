# domain/notifications

> Cross-org notification inbox and sidebar bell popover.

## Scope

- `NotificationsPage` (`index.tsx`) — full list at `/notifications`. Filter chips (all/unread/read); row click marks read; "Mark all read" bulk action.
- `NotificationsBell` — chrome composite at `apps/web/src/shared/components/chrome/notifications-bell.tsx`. Unread badge (99+ cap) + popover of up to 10 unread items + "Mark all read".

Does not own data — `QueryClient` lives in `main.tsx`.

## Public interface

- `NotificationsPage` — default export from `index.tsx`.
- `useNotificationsFilter` — logic hook in `use-notifications-filter.ts`. Returns `{ filter, setFilter }`. No JSX.

## Module architecture

- `NotificationsPage` renders the page shell and filter chips. Delegates data fetching to `<NotificationsList>` under `<ErrorBoundary>` + `<Suspense>`.
- `<ErrorBoundary>` uses `react-error-boundary` with `<ErrorBanner message="Couldn't load notifications." onRetry={...} />` fallback.
- `<Suspense>` fallback: five `<Skeleton>` rows.
- `useNotifications(filter)` — `useSuspenseQuery`; invalidated by mark-read mutations. Query keys: `["notifications", readState]`, `["notifications", "popover"]`.
- `groupByDate` — pure bucketing function (Today / Yesterday / This week / Older). Module-private.

## Data owned

- `["notifications", readState]` — list query.
- `["notifications", "popover"]` — popover query (owned by `NotificationsBell`, not this page).
- Local: `filter: ReadFilter` via `useNotificationsFilter`.

## How it's tested

Component/integration tests in `test/notifications.test.tsx` use Vitest + RTL + MSW. Tests assert rendered output against mocked HTTP responses — no `vi.mock` on `@core/api`. See [patterns.md § MSW testing strategy](patterns.md#msw-testing-strategy).
