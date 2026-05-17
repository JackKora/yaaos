# yaaos docs

Present-tense documentation for shipped code. Future-tense planning lives in [`/plan/`](../plan/).

## System-wide

- [setup.md](setup.md) — operator setup: Docker stack, GitHub App, Anthropic key, local-dev variant.
- [system-architecture.md](system-architecture.md) — runtime topology, inter-app flows, cross-app conventions.
- [glossary.md](glossary.md) — shared vocabulary across backend and UI.

## Per-app

Each app's docs live with its code.

- [`apps/backend/docs/`](../apps/backend/docs/README.md) — FastAPI service.
- [`apps/web/docs/`](../apps/web/docs/README.md) — React SPA.
- [`apps/fake-github/docs/`](../apps/fake-github/docs/README.md) — peer test service faking GitHub.
- [`apps/e2e/docs/`](../apps/e2e/docs/README.md) — Playwright suite.

## Conventions

- Present tense only. Unbuilt work lives in `plan/`.
- No decision history. Edit the doc; git log is the audit trail.
- Per-module docs share a fixed template: Purpose · Public interface · Module architecture · Data owned · How it's tested.

See [`/CLAUDE.md`](../CLAUDE.md) for the full working rules.
