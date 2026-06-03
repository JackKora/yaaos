# core/sidebar

> Nav sidebar — org-scoped nav tree, user card, collapse state, and nav config types.

## Scope

Owns the sidebar chrome: the nav tree with org-scoped links and a collapsible settings group, the user card popover (theme toggle, log-off, user-area links), and the per-group collapse state persisted to `localStorage`. Does NOT own the sidebar pin/unpin preference (that lives in `core/layout/public/theme.ts` as a layout concern).

- **Receives:** org slug and current user from `@core/api/public/`; sidebar pin state from `@core/layout/public/theme`.
- **Emits:** nothing — a pure rendering component.
- **Hands to:** `AppShell` in `core/layout`, which mounts `<Sidebar />` as the left rail.

## Public interface

Files under `core/sidebar/public/`, imported directly via `@core/sidebar/public/<file>`:

- `public/sidebar.tsx` — `Sidebar` — full sidebar component; mount once in `AppShell`.
- `public/user-card.tsx` — `UserCard` — bottom-of-sidebar user card with popover.
- `public/nav-config.ts` — `NavConfig`, `NavGroup`, `NavItem`, `NavLink`, `NavRole` — typed nav configuration shapes.

Private (non-`public/`): `use-collapse-state.ts`, `notifications-bell.tsx`, `org-switcher.tsx` — all internal to `Sidebar`; only `sidebar.tsx` imports them.

## Why / invariants

- **Role gate per item.** `role: "admin"` hides an item for builders; `role: "owner"` would hide it for admins too. Owner is mapped to `"admin"` effective role — there is no `"owner"` gate value.
- **Auto-collapse on navigation.** A group collapses when no child route is active. Users can manually re-expand; the next route change re-applies the rule. Prevents stale open groups after navigation.
- **Pin state in `core/layout/theme`.** The sidebar pin boolean is a layout preference, not a nav concern, so it lives in `theme.ts` alongside the theme preference.

## Gotchas

- `useCollapseState` persists to `localStorage` under `yaaos.sidebar.collapse`. Cross-tab sync via the `storage` event keeps two open windows coherent.
- `sidebar.tsx` imports `getSidebarPinned`/`setSidebarPinned` from `@core/layout/public/theme` — cross-module import from the already-migrated layout module.

## Vocabulary

- **Nav config** — typed tree of `NavLink` and `NavGroup` items; icons + paths injected by `sidebar.tsx`.
- **Collapse state** — per-group boolean (`true` = collapsed), keyed by group `id`, persisted to `localStorage`.

## Entry points

- `apps/web/src/core/sidebar/public/sidebar.tsx` — `Sidebar`.
- `apps/web/src/core/sidebar/public/nav-config.ts` — nav config types.
- `apps/web/src/core/sidebar/test/sidebar.test.tsx` — unit tests.
