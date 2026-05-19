# START HERE — M02 autonomous execution

> Read this top to bottom before doing anything. Re-read after every context compaction.

## Invocation

The user starts a Claude Code session and sends one message:

```
Execute the milestone at plan/milestones/M02-auth/START_HERE.md. Follow it exactly.
```

That is the only manual step. Everything below runs autonomously.

## Files that govern this run

- **This file** (`START_HERE.md`) — the ritual. Always re-read at phase boundaries and after compaction.
- **[PHASES.md](PHASES.md)** — the ledger. Checkboxes are the source of truth for "what's done." Tick as you go.
- **[requirements.md](requirements.md)** — locked spec. What the system must do.
- **[architecture.md](architecture.md)** — module layout, data model, middleware design.
- **[implementation-plan.md](implementation-plan.md)** — phased build order and prose detail.
- **[DECISIONS.md](DECISIONS.md)** — append-only log of low-certainty decisions made during the run.

## One-time setup (do this first, exactly once)

1. `git checkout main && git pull` (skip if already on main and clean).
2. `git status` must be clean before starting. If not, stop and ask the user. (This is the *only* stop-and-ask.)
3. `git checkout -b m02-auth`. All work for M02 lives on this branch.
4. Read `PHASES.md` end-to-end. Find the first phase with any unchecked `[ ]` item.

## The ritual (every phase)

For each phase, in order:

1. **Re-read this file + `PHASES.md` + the relevant phase block in `implementation-plan.md`.**
2. Work the unchecked items in that phase, in listed order.
3. For every code change, follow the project's standing rules in `CLAUDE.md`: TDD (red-green-refactor), update docs in the same commit, no hand-edits to `tach.toml`, no backward-compat shims, fix root causes not symptoms.
4. When the phase's items all appear done:
   - Run `apps/backend/bin/ci` if backend changed.
   - Run `apps/web/bin/ci` if web changed.
   - Run `apps/e2e/bin/ci` if Playwright tests changed.
   - All relevant CI must exit 0. If not, fix and re-run. Do not advance.
5. `git add` the changed files and commit. Commit message: `M02 Phase <N>: <short summary>`.
6. Edit `PHASES.md`: change every `[ ]` for this phase to `[x]`. Commit again as `M02 Phase <N>: tick ledger`. (Two commits per phase is fine.)
7. Move to next phase.

## Decision protocol

You will hit ambiguities the spec doesn't resolve. Do **not** stop and ask.

- Make the best decision you can.
- Rate your certainty 1–5 (1 = guess, 5 = obvious right answer).
- If certainty is **3 or higher**: proceed silently.
- If certainty is **below 3**: append an entry to `DECISIONS.md` using the format documented in that file. Then proceed.

## Definition of "milestone done"

All of these must be true:

- `grep -n '\[ \]' plan/milestones/M02-auth/PHASES.md` returns **zero matches**.
- `apps/backend/bin/ci` exits 0.
- `apps/web/bin/ci` exits 0.
- `apps/e2e/bin/ci` exits 0.
- `git status` on branch `m02-auth` is clean.
- A summary of work + the contents of `DECISIONS.md` (low-certainty calls) is written to the final assistant message.

Do not declare done until all five conditions hold. If any fails, identify the failing condition, fix it, and re-verify.

## Compaction-survival contract

Context compaction will happen during this run. After every compaction:

1. Re-read `START_HERE.md` (this file).
2. Re-read `PHASES.md` to learn current progress.
3. Resume at the first phase with unchecked items.
4. Do not assume any in-memory state survived. The filesystem and git log are the truth.

## What NOT to do

- Do not skip ahead to a later phase before the current phase's items are all checked.
- Do not silently soften a failing test or assertion.
- Do not modify `apps/backend/tach.toml` by hand — run `apps/backend/bin/sync_modules`.
- Do not commit `.env` files or secrets.
- Do not push the branch. The user reviews and pushes when M02 is done.
- Do not delete `plan/notes/users_orgs_auth.md` until Phase 14 explicitly says to.
