# <one-line architecture summary>

> Current state lives in [./requirements.md § Current state](./requirements.md#current-state). This doc is target + delta only.

## Approach

<short narrative of technical direction. Each load-bearing claim that's a *change* cites the current `file:line` it diverges from inline — e.g., "shift dispatcher from polling (`apps/backend/app/domain/reviewer/queue.py:200`) to event-driven".>

## Boundaries touched

- **Service boundaries:** <backend↔web, backend↔agent, etc.>
- **Module-within-service boundaries:** <module ↔ module>

## Entities & value objects

| Name | Kind | New/Changed | Lives in | Notes |
|---|---|---|---|---|
| <Entity> | entity / value object | new / changed | <service.module> | <new: one-line rationale. changed: `was @ path:line → is`.> |

Notes-column format: `new` rows write a one-line rationale; `changed` rows write `was @ path:line → is <new>`.

## Interface changes

### <Boundary A>

**Current anchor:** `<path:line>` — <canonical current entry-point for this boundary (handler, queue consumer, route)>

| Change | Signature / endpoint / payload / event | Notes |
|---|---|---|
| added | <sig> | <one-line rationale> |
| changed | <sig> | `was: <sig> @ path:line → is: <new sig>` |
| deleted | <sig> | `was: <sig> @ path:line` |

<repeat per boundary, each with its own Current anchor>

## Sequence diagrams

<ASCII, one block per affected boundary, only when call sequence changes. Each block carries today (top) and after (bottom), separated by a horizontal rule. Cite the current entry-point `path:line` above the "today" half. Mark entities. Embed inline AND save the combined block to diagrams/<name>.txt — one file per boundary, both states inside.>

<If no sequence changes: write "No sequence changes." and omit the diagrams/ directory entirely.>

## Data model changes

- **Tables:** <added / changed / dropped. `changed` and `dropped` cite current migration / model `path:line`; `changed` writes `was → is`.>
- **Columns:** <added / changed / dropped. Same format rule as Tables.>
- **Migrations:** <forward + rollback notes>

## Open questions

- <architectural-level unknowns — distinct from requirements.md and plan.md lists>
