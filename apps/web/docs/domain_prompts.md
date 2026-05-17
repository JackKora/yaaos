# domain/prompts

> Editor for the three built-in reviewer agents' prompt text.

## Purpose

The `/prompts` page. One card per built-in reviewer agent (architecture / security / style); each has a `<textarea>` showing the agent's current `prompt_text`, a Save button, and a Reset-to-default button. Saved prompts take effect on the next review immediately.

## Public interface

- `PromptsPage` — mounted by `core/routing` at `/prompts`. Single-component module.

## Module architecture

`apps/web/src/domain/prompts/index.tsx` is a single ~65-LOC file. Reads `useReviewerAgents()` (`GET /api/reviewer/agents`) and renders one `<Card>` per agent.

### Draft state

Each `<textarea>` is controlled. The component holds a `drafts: Record<string, string>` keyed by agent name; initial value is seeded from `agent.prompt_text` once the query resolves, via a `useEffect` that only writes if no draft exists yet — so cache refreshes don't clobber unsaved edits.

### Save / reset

- **Save** (`save-${agent.name}`) — `useUpdateAgentPrompt` → `POST /api/reviewer/agents/${name}/prompt` with `{prompt_text: draft}`. Invalidates `["reviewer", "agents"]`. The draft stays so the operator can keep editing.
- **Reset to default** (`reset-${agent.name}`) — `useResetAgentPrompt` → `POST /api/reviewer/agents/${name}/reset` (returns the freshly-reset agent). The local draft is replaced with the returned `prompt_text`.

### Audit trail

Every save and reset writes a `reviewer_agent.prompt_updated` audit entry on the backend (`domain/reviewer.agent_crud`); the payload carries prior + new prompt hashes (not the full text — 100KB+ prompts would bloat the audit log). No FE display.

### No validation

Backend enforces non-empty `prompt_text` and returns 400 with a field-keyed error map; the FE doesn't pre-validate (dumb-FE pattern). An empty save would have to be entered deliberately to hit this path; the form doesn't yet display the inline error.

## Data owned

None. Agent rows live in the backend's `reviewer_agents` table (owned by `domain/reviewer`).

## How it's tested

No dedicated tests — the UI is a thin textarea + Save wrapper. Backend `agent_crud` has unit coverage at `apps/backend/app/domain/reviewer/test/`. An e2e spec is a candidate addition when the form gains validation or richer state.
