# core/primitives

> Foundational value objects and the `spawn()` helper. Bottom of the dependency tree.

## Purpose

The floor of the backend dependency tree. Other core modules, all domain modules, and all plugins may depend on it; it depends on nothing yaaos-specific. Holds value objects used widely enough that no single module owns them, plus `spawn()` — the fire-and-forget wrapper every background coroutine goes through.

## Public interface

Exported from `app/core/primitives/__init__.py`:

- `Actor` / `ActorKind` — who-did-what value object + enum.
- `PluginMeta` / `PluginType` — plugin self-description + the `"vcs" | "coding_agent" | "workspace"` literal.
- `spawn(name, coro)` — fire-and-forget background task launcher.
- `active_task_count()` — test helper; number of pending spawned tasks.

No HTTP routes. No tables.

## Module architecture

### `Actor`

Single who-did-what value object. Three kinds:

- `github_user` — requires `login`; `agent_id` must be `None`.
- `agent` — requires `agent_id` (UUID); `login` must be `None`.
- `system` — both `None`.

Invariants enforced via a Pydantic `model_validator(mode="after")` — wrong shapes raise at construction. Three convenience classmethods (`Actor.system()`, `Actor.github_user(login)`, `Actor.agent(agent_id)`). Consumed by `core/audit_log`, `domain/reviewer`, `domain/intake`, and any code recording who initiated something.

### `PluginMeta`

Self-description every plugin exposes via `meta`. Fields: `id` (stable code identifier — registry key, URL prefix, FK string), `type`, `display_name`, optional `description`, optional `docs_url`. `meta.id` is the canonical accessor across the codebase. Settings page iterates `PluginMeta` from the three registries instead of hardcoding.

### `spawn()`

Every background coroutine goes through this helper. Wraps `coro` in a try/except that logs `spawn.crashed` with a stack trace, calls `asyncio.create_task`, and adds the task to a module-level `_tasks: set` (the standard asyncio GC guard); `add_done_callback(_tasks.discard)` cleans up on completion.

Contract:

- **Fire-and-forget.** Caller does not await.
- **Last-resort safety net.** If the coroutine raises, `spawn()` swallows + logs; the coroutine is expected to mark its own domain row failed first.
- **Cancellation is cooperative.** No external cancel signal — the coroutine polls DB state at safe points and exits itself.

Used for the workspace reaper, GitHub catch-up poller, and every async background flow domain modules launch. Not used for anything a caller will `await`. `active_task_count()` returns pending tasks; tests use it to assert background work drained.

## Data owned

None. `_tasks` is in-memory only.

## How it's tested

`app/core/primitives/test/`:

- `test_actor.py` — invariant enforcement per `ActorKind`.
- `test_spawn.py` — runs the coroutine, swallows + logs exceptions, removes the task on completion.

`PluginMeta` is exercised by every plugin's registration test and the settings discovery endpoint.
