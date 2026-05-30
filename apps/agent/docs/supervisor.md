# supervisor

> Coordinates identity exchange, claim/heartbeat/sweep loops, workspace command routing, and goroutine lifecycle for the `agent supervisor` subcommand.

## Scope

- **Owns:** identity exchange (STS → bearer), N concurrent claim-loop workers, heartbeat loop, per-command routing to the pool, activity-WebSocket management, bearer-refresh loop, and disk-sweep loop.
- **Does not own:** workspace subprocess execution (that's `internal/workspace`), wire type definitions (`internal/protocol`), or command encoding (`internal/command`).
- **Receives:** raw `[]byte` from `protocol.Client.ClaimCommand`; hands to `command.Decode`.
- **Emits:** typed `protocol.AgentEvent` to `protocol.Client.PostCommandEvent` after each dispatch.
- **Hands to:** `Pool.Dispatch` for workspace commands; `AgentCommand.Execute(s)` for supervisor-resident commands.

## Why / invariants

- **Single pool mutex guards the registry.** All state reads/writes to workspace records go through `Pool`'s named mutators. No free-form field access.
- **Heartbeat reads `pool.Snapshot()`** — a pure projection of the registry state. It reports every registered workspace (Active/Defunct/Orphaned), not just in-flight ones.
- **Disk sweep reads `pool.KnownIDs()`** — covers Active, Defunct, and Orphaned. A Defunct record keeps its id in KnownIDs so the sweep never removes a directory the registry knows about.
- **Orphan startup scan calls `pool.seedOrphan(id, path)`** per found directory, so the first heartbeat after a pod restart correctly reports leftover workspaces as `status="unknown"`.
- **Forgotten-workspace janitor reads `pool.Paths()`** — includes every record that has a path set. After `os.RemoveAll` succeeds, calls `pool.remove(id)` to drop the record.
- **Busy-ness is tracked inside `Pool.Dispatch`** — `setCommandID`/`clearCommandID` toggle `current_command_id` around Send. A completed command's workspace stays `status="running"` until the backend explicitly reaps it.

## Gotchas

- `CloseAll` on shutdown: pool reaps all runners; already-nil runners (Orphaned records) are skipped.
- The activity-WS conductor is torn down before `CloseAll` to avoid a slow-flush race on ctx cancel.
- Bearer refresh loop runs independently on its own backoff — a failed STS exchange does not affect the heartbeat or claim schedules.

## Vocabulary

- **Orphan** — a workspace directory found on disk at startup from a prior run. Seeded into the registry as Orphaned; the backend signals cleanup via `forgotten_workspaces`.
- **Forgotten** — a workspace the backend no longer tracks; named in `HeartbeatResponse.forgotten_workspaces`. The janitor removes its directory and drops the registry record.
- **Defunct** — a workspace whose runner exited unexpectedly (child-exit). Stays in the registry (and thus in KnownIDs) until the backend reaps it. See [workspace_lifecycle.md](workspace_lifecycle.md).

## Entry points

- `apps/agent/internal/supervisor/supervisor.go` — `Supervisor` struct, `New`, `Run`, goroutine wiring.
- `apps/agent/internal/supervisor/pool.go` — registry, state machine, `Dispatch`.
- `apps/agent/internal/supervisor/reconciliation.go` — startup scan, disk sweep, forgotten-workspace janitor.
