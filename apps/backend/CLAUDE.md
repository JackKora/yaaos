# Backend — editing rules

- **No cross-module test-helper exports.** A `core`/`domain`/`plugins` module must never put a test-seam name (`reset_*`, `clear_*`, `scoped_*`, `*_for_tests`, `_seed_*`, `set_*_override`, `set_test_*`, `get_test_*`) in its `__all__` if no production code imports it. `bin/sync_modules` enforces this at every CI run (exit 2 on violation). See [docs/patterns.md § Module boundaries in tests](docs/patterns.md) for the full rule.

- **Cross-module test machinery lives in `app/testing/`.** `app/testing/isolation`, `app/testing/seed`, and `app/testing/workflow_harness` are the correct home for cross-module fixtures, seed helpers, and workflow-engine harness helpers. Never import a reset/clear/seed seam directly from a `core`/`domain`/`plugins` module in a test outside that module's own `test/` directory.

- **Read `docs/architecture.md` and `docs/patterns.md` before editing any module.** These docs own the decisions that look arbitrary in code.
