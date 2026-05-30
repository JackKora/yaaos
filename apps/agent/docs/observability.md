# internal/observability

> Wires the WorkspaceAgent's OpenTelemetry SDK and declares the standard metric/span dimensions.

## Scope

- **Owns:** `Init` (SDK bootstrap — traces, metrics, logs), `Instruments` (metric instruments), `SetStandardDimensions`/`StandardAttrs` (org_id + agent_id on metrics), `bindMetrics` (instrument resolution).
- **Does not own:** the base slog logger (owned by `internal/logging`), span creation (owned by `internal/tracing`), or identity exchange (owned by `internal/identity` + `internal/supervisor`).
- **Receives:** `Config{ServiceVersion, AgentPodID}` at startup; `(orgID, agentID)` pair after identity exchange.
- **Emits:** OTel resource + SDK providers wired into the global `otel.*` registries; `Result.SlogHandler` for the logging fan-out.

## Standard dimensions

Every signal carries two kinds of attributes:

- **Resource attributes** (pod-level, static for the process lifetime):
  - `service.name` = `yaaos-workspace-agent`
  - `service.version` = binary version
  - `service.instance.id` = `agent_pod_id` — the per-pod identifier persisted locally and reported on heartbeat.
- **Span / metric attributes** (set after identity exchange):
  - `org_id` — the org this pod belongs to; pinned on first identity exchange.
  - `agent_id` — the `workspace_agents` row PK; pinned on first identity exchange.

`agent_pod_id` is resource-only because it's known before identity exchange and belongs to the OTel resource model. `org_id` and `agent_id` are span/metric attributes because they're assigned by the backend; they appear after `SetStandardDimensions` is called from the supervisor.

## Resource vs attribute split — why

OTel resources describe the emitting entity (the pod). Span/metric attributes describe the event. Putting `org_id`/`agent_id` on the resource would require rebuilding the SDK before those values are known; attaching them as attributes avoids that. Cardinality is safe: orgs and agents are few.

## Local vs OTLP output

- **OTLP disabled** (`OTEL_EXPORTER_OTLP_ENDPOINT` unset): `Init` is a no-op. Instruments resolve through the SDK no-op provider; `Metrics()` call sites work without nil-checking. No goroutines start.
- **OTLP enabled**: traces/metrics/logs flow to the configured OTLP/HTTP endpoint. Customers configure their own collector (Datadog, Honeycomb, etc.) downstream; the agent speaks OTLP only.

## Per-command dimensions

The supervisor adds `workspace_id` and `command_id` as span attributes on the `supervisor.dispatch.<kind>` span for each command (see `internal/supervisor`). These are span-scoped, not process-wide.

## Instruments summary

Key counters emitted by the supervisor (all carry `org_id` + `agent_id`):

| Instrument | Extra attributes | Meaning |
|---|---|---|
| `yaaos.agent.commands.deduped` | — | Duplicate `command_id` hit the dedup cache; no re-execution |
| `yaaos.agent.events.post.retries` | `kind` | Each retry of a terminal-event POST (transient failure) |
| `yaaos.agent.commands.completed` | `result` | Terminal dispatch outcome (success / failure / timeout) |
| `yaaos.agent.connection.failures` | `surface`, `class` | Auth or network failures per connection surface |

## Gotchas

- `bindMetrics` is called from `Init` after the real provider installs, swapping out no-op instruments. Tests that call `Metrics()` before `Init` get no-ops — fine for unit tests; service tests need the real provider only if they assert metric values.
- `SetStandardDimensions` is safe to call concurrently (guarded by `stdDimsMu`); it's a process-wide singleton, called once after identity exchange.

## Entry points

- `apps/agent/internal/observability/otel.go` — `Init`, `Config`, `Result`.
- `apps/agent/internal/observability/metrics.go` — `Instruments`, `Metrics()`, `SetStandardDimensions`, `StandardAttrs`.
