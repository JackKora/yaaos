# core/layout

> App shell — sidebar mount, route outlet, theme tokens, broken-integrations banner.

## Purpose

Wraps every signed-in page in the sidebar-only shell mandated by [design.md § Layout](design.md#layout). Owns the theme switcher (`data-theme` on `<html>`) and the in-page banner that surfaces broken integrations across the top of `<main>`. The sidebar itself lives in [core/sidebar](../src/core/sidebar/) and is composed into the shell here.

## Public interface

- `AppShell` — root-route component (see [core_routing.md](core_routing.md)). The only export.

## Module architecture

### Files

Under `src/core/layout/`: `app-shell.tsx`, `theme.ts`, `broken-integrations-banner.tsx`, with `index.ts` re-exporting `AppShell`. The sidebar is its own module — see [core/sidebar/](../src/core/sidebar/).

### `AppShell`

Two-column flex: fixed-width sidebar on the left, flexible-width content on the right. Only `<main>` scrolls; the sidebar stays pinned. There is **no top bar** — the sidebar is the only persistent chrome (see [design.md § Principles](design.md#principles)). Above `<main>`, the `BrokenIntegrationsBanner` renders inline when any required integration is unhealthy.

`STANDALONE_PATHS` (`/login`, `/user`, `/orgs`) render the `<Outlet />` without the shell — user-scoped + org-picker pages don't surface org nav. Visiting a standalone path while authenticated still works; visiting one of the org-scoped paths while unauthenticated bounces through `indexRoute → /login`.

### Theme tokens

`theme.ts` exposes a small helper API used by the sidebar's pin toggle and the user-card theme switch:

- `getSidebarPinned()` / `setSidebarPinned(pinned)` — persist the pinned-vs-rail state to `localStorage`.
- `toggleTheme()` — flip `[data-theme="light"|"dark"]` on `<html>` and persist the choice.

Color and spacing values are CSS custom properties defined in [`src/styles.css`](../src/styles.css) and aliased onto Tailwind utilities in `tailwind.config.ts`. The token vocabulary is documented in [design.md § Design tokens](design.md#design-tokens). `:root` defaults to dark; values flip when `[data-theme="light"]` is set.

### `BrokenIntegrationsBanner`

Renders inside the shell, above `<main>`, when `useBrokenIntegrations()` returns a non-empty list. One row per broken integration, with a deep link to the relevant settings page. Hidden entirely when everything is healthy.

## Data owned

None — `BrokenIntegrationsBanner` reads from a query hook; `theme.ts` reads/writes `localStorage` only.

## How it's tested

Rendered on every e2e test — any shell breakage shows up as page-navigation test failures. Sidebar has its own unit tests under `core/sidebar/test/`.
