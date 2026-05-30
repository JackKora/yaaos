# Workspace lifecycle

> The pool registry as single owner of workspace state, with two orthogonal tracking axes.

## Registry as single owner

The `Pool` (`apps/agent/internal/supervisor/pool.go`) holds one `workspaceRecord` per workspace_id in a mutex-guarded map. It is the authoritative source for workspace status, directory path, and busy-ness. Every state change goes through named Pool mutators; every read goes through named Pool read methods.

## Two axes

Each record tracks two independent concerns:

| Axis | Field | Meaning |
|---|---|---|
| Liveness | `WorkspaceState` | Is the subprocess running, gone, or from a prior run? |
| Busy-ness | `current_command_id` | Is a command executing right now? |

These are orthogonal. A live workspace with no in-flight command has `state=Active, current_command_id=""` — it is idle but still running, and the heartbeat correctly reports `status="running"`.

## Liveness states

| State | `status` in heartbeat | Runner | When entered |
|---|---|---|---|
| `Active` | `"running"` | non-nil | `createActive` on first CreateWorkspace |
| `Defunct` | `"exited"` | closed (was non-nil) | `markDefunct` on unexpected child exit |
| `Orphaned` | `"unknown"` | nil | `seedOrphan` at startup scan |

## Transition table

Each edge is a named Pool mutator — no direct state writes.

| From | To | Mutator | Trigger |
|---|---|---|---|
| (absent) | Active | `createActive` | CreateWorkspace dispatch |
| (absent) | Orphaned | `seedOrphan` | startup scan finds leftover dir |
| Active | Defunct | `markDefunct` | runner Send returns an error (child exited or timed out) |
| any | (removed) | `remove` | CleanupWorkspace succeeds, or backend forgotten-workspaces janitor completes |

Busy-ness transitions:
- `setCommandID(id, cmd)` — called when Dispatch begins Send
- `clearCommandID(id)` — called (deferred) when Dispatch returns

## Read methods

- `Snapshot() []HeartbeatWorkspaceEntry` — heartbeat payload; status derived from state, current_command_id carried verbatim.
- `KnownIDs() map[string]struct{}` — every record, all three states; disk sweep only removes dirs whose id is NOT in this set.
- `Paths() map[string]string` — id → path for records with a path set; used by the forgotten-workspaces janitor.
- `ActiveIDs() []string` — Active-state ids only.

## Orphan record shape

An Orphaned record has a nil runner and a path set from the startup scan. It is in `KnownIDs` so the disk sweep leaves its directory intact. The backend decides its fate via `HeartbeatResponse.forgotten_workspaces`; the janitor calls `remove` after `os.RemoveAll` succeeds.

## Defunct record shape

A Defunct record has a closed runner (kept in the struct but not used for Sends). It stays in `KnownIDs` — the directory is protected until the backend reaps it. A subsequent `CreateWorkspace` for the same id replaces the Defunct record with a fresh Active one (`createActive` overwrites the registry entry).
