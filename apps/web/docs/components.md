# Components

> Index of the React primitives + composites available in the SPA. Domain-specific composites live in their feature module and aren't listed here.

## Three-layer model

| Layer | Location | What lives here |
|---|---|---|
| **Vendor / primitive** | `src/shared/components/ui/` | Vendored shadcn/Radix primitives. No domain logic, no restyling inside a primitive — wrap in a composite instead. |
| **Composite** | `src/shared/components/public/{layout,chrome}/` | Presentational, cross-feature composites (`PageHeader`, `EmptyState`, `ErrorBanner`, `OrgSwitcher`, …). No feature-specific data fetching. |
| **Feature** | `src/domain/<module>/` | Domain-specific components that colocate with their module. Graduate to composite on the 2nd/3rd consumer (rule-of-three). |

**Rule-of-three graduation:** a feature component moves to `shared/components/` once it has real consumers in two or more unrelated domain modules. Don't pre-graduate — leave it in `domain/<m>/` until it earns its place.

**Vendor-layer carve-out:** shadcn/Radix primitives in `ui/` may hand-roll ARIA patterns and focus management internally — that's the vendor's job, not ours. Don't add domain logic or hardcoded copy inside those files.

`src/shared/components/`: `ui/` (shadcn/Radix primitives), `public/layout/` (page header, empty state, error banner). All live in-repo — modify freely. The chrome components (`OrgSwitcher`, `NotificationsBell`) and the org-gate banner (`NotConfiguredBanner`) moved to `core/sidebar/` and `core/layout/public/` respectively — they use `@core/api` hooks and so cannot live in `shared/`.

## Primitives (`src/shared/components/ui/`)

### Form

| File | Purpose |
|---|---|
| `button.tsx` | All clickable affordances. Variants: `default`, `destructive`, `outline`, `secondary`, `ghost`, `link`. |
| `input.tsx` | Single-line text inputs. |
| `textarea.tsx` | Multi-line text inputs. |
| `select.tsx` | Native-feel dropdown select, Radix-driven. |
| `checkbox.tsx` | Boolean field. |
| `switch.tsx` | Boolean field — preferred over Checkbox for instant-apply settings. |
| `label.tsx` | Form labels — associates via `htmlFor`. |
| `form.tsx` | `react-hook-form` integration (FormField, FormItem, FormControl, FormMessage). |

### Overlays

| File | Purpose |
|---|---|
| `dialog.tsx` | Modal dialog. Composed by ConfirmModal / PickerModal. |
| `popover.tsx` | Anchored floating panel. Used by Org switcher, Notifications. |
| `dropdown-menu.tsx` | Menu list anchored to a trigger. |
| `tooltip.tsx` | Hover/focus tooltip. |
| `sheet.tsx` | Side-anchored drawer. Required transitively by the shadcn `sidebar` primitive's mobile collapse — yaaos's navigation doesn't expose a drawer pattern. |

### Display

| File | Purpose |
|---|---|
| `table.tsx` | Semantic table primitives (`Table`, `TableHeader`, `TableRow`, `TableCell`, …). |
| `badge.tsx` | Status pills. Variants: `default`, `secondary`, `destructive`, `outline`. |
| `avatar.tsx` | Initials avatar with optional image fallback. |
| `separator.tsx` | Horizontal/vertical divider. |
| `skeleton.tsx` | Loading placeholder. |
| `tabs.tsx` | In-page tab navigation. |

### Layout

| File | Purpose |
|---|---|
| `sidebar.tsx` | shadcn sidebar primitive — handles collapse, sub-items, mobile-sheet fallback. yaaos composes a `Sidebar` on top. |
| `collapsible.tsx` | Inline expand/collapse panel. |
| `scroll-area.tsx` | Custom-scrollbar viewport. |

### Toast

| File | Purpose |
|---|---|
| `sonner.tsx` | Wraps `sonner` for theme-aware toasts. Rendered once in `main.tsx`. |

## Layout composites (`src/shared/components/public/layout/`)

Public surface of the `shared/components` module. Import directly via `@shared/components/public/layout/<file>`.

| File | Export | Purpose |
|---|---|---|
| `page-header.tsx` | `PageHeader` | Title + optional subtitle + right-aligned actions slot. The first composite on every surface. |
| `empty-state.tsx` | `EmptyState` | Icon + headline + body + optional action; the C2 empty-list pattern. |
| `error-banner.tsx` | `ErrorBanner` | In-page error with optional Retry. Voice rule (D3): blames the system, not the user. |
| `confirm-modal.tsx` | `ConfirmModal`, `ConfirmTone` | Destructive + cost-protective variants share the shell; copy differs (D3). |
| `picker-modal.tsx` | `PickerModal`, `PickerOption` | "Add X" flows (plugin type, integration provider). Lists `PickerOption[]`; caller wires the post-pick route push. |

## Hooks (`src/shared/hooks/public/`)

Public surface of the `shared/hooks` module. Import directly via `@shared/hooks/public/<file>`.

| File | Export | Purpose |
|---|---|---|
| `use-mobile.ts` | `useIsMobile` | Returns `true` when the viewport is below the mobile breakpoint. Used by shadcn `sidebar`. |

## Adding a primitive

`pnpm dlx shadcn@latest add <name> --yes`. If the CLI rewrites `src/styles.css` or attempts to add a `tailwind.config.ts`, discard the config file (Tailwind v4 is CSS-first; no JS config) and reconcile any token additions against the `@theme` + `@layer base` structure in `src/styles.css`. Add a one-liner to this doc.
