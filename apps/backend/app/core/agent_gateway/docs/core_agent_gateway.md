# core/agent_gateway

> Wire protocol and in-memory dispatch between the control plane and customer-deployed WorkspaceAgents.

## Scope

- **Owns:** per-agent in-memory FIFO, claim long-poll, lifecycle-gated dispatch, heartbeat reconciliation, event ingestion with stale-claim guard, identity-exchange writer, `WorkspaceAgentReportSink` protocol, `workspace_agents` row management.
- **Does not own:** workspace state (delegates to `core/workspace` via `WorkspaceAgentReportSink`), workflow advancement (delegates to `core/workflow` via outbox), bearer token ledger (delegates to `core/agent_gateway/bearers`).
- **Receives:** HTTP requests from the Go WorkspaceAgent (wire types in `types.py`, OpenAPI spec in `openapi/agent-api.yaml`).
- **Emits:** `AgentCommand` to the agent on claim; `HeartbeatResponse.forgotten_workspaces` for reconciliation; enqueues `HANDLE_AGENT_EVENT` outbox task on terminal events.

## Lifecycle gate + claim gating

- **Unconfigured claim** — the agent sends `lifecycle="unconfigured"`. The backend returns a `ConfigUpdateCommand` built from the org/global `max_workspaces` default. No workspace commands are dequeued regardless of queue depth. The agent accumulates queued commands while bootstrapping.
- **Configured claim** — the agent sends `lifecycle="configured"` and `active_workspace_ids`. The backend returns the first *eligible* queued command:
  - `ConfigUpdateCommand`: always eligible.
  - `CreateWorkspaceCommand`: always eligible (creates a new Active workspace).
  - Other workspace commands: eligible only when `workspace_id ∈ active_workspace_ids`.
  - Ineligible commands remain at their queue position.

## `max_workspaces` source

`DEFAULT_MAX_WORKSPACES` in `service.py` is the global default. There is no per-agent or per-org column at this time; all agents share the same default. The value travels in `ConfigUpdateCommand.config.max_workspaces`.

## ConfigUpdate kind

`AgentCommandKind.CONFIG_UPDATE = "ConfigUpdate"` is the discriminator value. The command carries `AgentConfig{max_workspaces, otlp_endpoint, otlp_token, otlp_dataset}`. `otlp_token` is a secret — never log it.

## Stale-claim guard

`record_agent_event` delegates stale-claim lookup to `WorkspaceAgentReportSink.resolve_claim`. A mismatch raises `StaleClaimError`; the endpoint returns `410 Gone`.

## Identity exchange

`ensure_agent_row` upserts the `workspace_agents` row. The response includes `org_id` so the agent can pin it for identity-integrity checks on renewal.

## Entry points

- `apps/backend/app/core/agent_gateway/service.py` — FIFO, `claim_next`, `record_agent_event`, heartbeat.
- `apps/backend/app/core/agent_gateway/types.py` — Pydantic wire types.
- `apps/backend/openapi/agent-api.yaml` — authoritative schema (drift-detected by `test_openapi_mirror_drift.py`).
