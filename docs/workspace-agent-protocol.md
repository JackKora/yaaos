# WorkspaceAgent wire protocol

> Control-plane ↔ WorkspaceAgent contract: channels, lifecycle, claim routing, auth, and ordering conventions.

## Channels

Five HTTPS endpoints + one WebSocket under `/api/v1/`. See `apps/backend/openapi/agent-api.yaml` for schemas.

| Endpoint | Direction | Purpose |
|---|---|---|
| `POST /api/v1/identity/exchange` | Agent → CP | STS-signed bootstrap → 24h bearer |
| `POST /api/v1/agents/{id}/heartbeat` | Agent → CP | Liveness + workspace inventory; CP returns reconciliation hints |
| `POST /api/v1/agents/{id}/commands/claim` | Agent → CP | Long-poll for next command (≤55s) |
| `POST /api/v1/commands/{id}/events` | Agent → CP | Progress + terminal AgentEvent |
| `POST /api/v1/workspaces/{id}/events` | Agent → CP | Workspace state transitions |
| `WSS /api/v1/agents/{id}/activity` | Bidirectional | High-frequency activity streaming; demand-pull |

## `unconfigured → configured` state machine

A fresh agent (or any restarted pod) enters the `unconfigured` lifecycle.

**Unconfigured:**
- Claim requests carry `lifecycle="unconfigured"`.
- The control plane returns a `ConfigUpdateCommand` (kind `"ConfigUpdate"`) on every unconfigured claim, regardless of queue depth.
- Workspace commands are not dequeued; they accumulate until the agent is configured.
- The agent rejects any `WorkspaceCommand` that arrives before configuration with `completed_failure "agent unconfigured"`.

**Transition:** `ConfigUpdateCommand.Execute` stores the config atomically. The agent's lifecycle immediately becomes `configured`.

**Configured:**
- Claim requests carry `lifecycle="configured"` + `active_workspace_ids` (the IDs of currently running workspaces).
- The control plane returns the first *eligible* queued command.
- A process restart returns to `unconfigured` (the atomic pointer is not persisted).

## Claim routing — `active_workspace_ids`

Eligibility on a configured claim:
- `ConfigUpdateCommand` — always eligible.
- `CreateWorkspaceCommand` — always eligible (creates a new workspace).
- Other workspace commands — eligible only when `workspace_id ∈ active_workspace_ids`.
- Ineligible commands stay in the queue; the next eligible command is returned instead.

This prevents the agent from receiving a command for a workspace it no longer holds in its registry.

## Bearer auth + renewal

- The agent submits a pre-signed STS `GetCallerIdentity` on identity exchange; the backend issues a 24h bearer.
- The agent re-exchanges before the bearer expires (`bearerRefreshLoop`). A renewal response that returns a different `agent_id` or `org_id` than the original exchange is an identity-integrity violation; the agent exits fatally.
- The agent pins `agent_id` + `org_id` from the first exchange and carries them on every log/span/metric.

## Ordering + idempotency

- Commands are FIFO per agent. Eligible commands are dequeued in order; ineligible commands hold their position.
- Each command carries a `command_id` (UUID). The stale-claim guard on the backend matches the posted event's `command_id` against the workspace's current claim; a mismatch returns `410 Gone`.
- The agent posts the terminal event exactly once per dispatch. Event-post reliability (retry + dedup) is addressed separately from this contract.

## ISO-UTC wire convention

All `datetime` fields use ISO 8601 with `Z` suffix (UTC). Pydantic emits `Z`-suffixed strings; the Go agent formats with `time.RFC3339`.

## Schema reference

`apps/backend/openapi/agent-api.yaml` — authoritative spec. `app/core/agent_gateway/types.py` is the hand-written Pydantic mirror; drift is detected by `test_openapi_mirror_drift.py`. The Go agent's wire types live in `apps/agent/internal/protocol/types.go`.
