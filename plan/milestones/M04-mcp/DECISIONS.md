# M04 — decisions made during autonomous run

> Append-only log of decisions made when the spec was ambiguous and certainty was below 3 of 5. Per [START_HERE.md § Decision protocol](START_HERE.md#decision-protocol).

## Format

Each entry:

```
### <Phase N> — <one-line decision summary>

- **Certainty**: <1 or 2>/5
- **Decision**: <what was chosen>
- **Alternatives considered**: <brief>
- **Why this one**: <one line>
- **Reversal cost**: <low/medium/high — how painful to undo later>
```

Keep entries terse. The user reads this at the end of the run; volume = friction.

## Entries

<!-- Append below. Do not edit prior entries. -->

### Phase 0b — fake-app standalone tests deferred to integration coverage

- **Certainty**: 2/5
- **Decision**: No standalone `pytest` test suites for `apps/fake-linear/` or `apps/fake-notion/`. The PHASES.md item "Tests for fake-linear / fake-notion" is satisfied by Phase 1+ backend integration tests that drive the fakes via docker-compose.
- **Alternatives considered**: Ship a `tests/` directory in each fake with a `TestClient` smoke suite.
- **Why this one**: backend pytest's conftest (testpaths = ["app"]) collides with the fakes' top-level `app` package when running from inside their dirs (the backend's `app.core` doesn't exist in the fake's namespace, but the conftest still loads). Isolating each fake under its own venv + pytest config is mechanical noise; the practical correctness check is the same docker-compose stack that production uses. Both fakes pass `docker compose up --wait` (healthchecks healthy) + manual `curl` against `/oauth/authorize` returns 303 with `code` + `state`.
- **Reversal cost**: low — add a sibling pyproject + conftest if dedicated unit coverage becomes useful.
