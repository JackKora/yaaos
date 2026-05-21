# M05 Requirements — Workspace Agent

> Locked decisions and open questions for the workspace agent milestone.

## Why this milestone

yaaof needs to act on customer source code without that code crossing yaaof infrastructure. The workspace agent is the customer-deployed worker that holds the code, runs coding agents (Claude Code etc.) against it, and reports only findings + agent telemetry back. It is the realization of the trust boundary the architecture has assumed since the project began.

This milestone delivers:

- The agent itself (`apps/agent/`, Go).
- New control-plane modules (`core/agent_gateway`, `core/workflow`, `domain/intake`, `domain/ticket`).
- Extensions to existing modules (`core/workspace`, `domain/reviewer`, `domain/coding_agent`).
- A formalized Workflow + WorkflowCommand model that generalizes today's `review_job` pattern into a substrate that supports future workflows (investigation, planning, implementation, HITL).

## Locked decisions

### Language, deployment, packaging

- **Go.** Single static binary, ~15MB container, native subprocess/signal handling, first-class AWS SDK.
- **Public Docker image.** Customer pulls and runs in ECS/Fargate. No customer-side build/install.
- **Monorepo location:** `apps/agent/`.
- **API contract:** hand-written OpenAPI in `apps/backend/openapi/agent-api.yaml`. Pydantic codegen for backend; oapi-codegen for agent. Both regenerate in CI.

### Backend module map

Final layout. Dependencies flow downward; no cycles.

| Module | Layer | Responsibility |
|---|---|---|
| `core/agent_gateway` (new) | core | Wire protocol. HTTP endpoints agents hit (identity exchange, command claim, heartbeat, event ingestion). Per-agent in-memory command queue. Agent registry. The only module that talks to remote agents. |
| `core/workspace` (extended) | core | Workspace records, lifecycle state machine, single-flight enforcement, provisioning policy, recovery policy, audit log. **Provides workspace-lifecycle WorkflowCommands** (`CreateWorkspace`, `CleanupWorkspace`, `RefreshWorkspaceAuth`). Provider abstraction supporting `in_memory` and `remote_agent` implementations. |
| `core/workflow` (new) | core | **Engine mechanics only.** `Workflow` data structure, `WorkflowCommand` interface, registry, state machine, transition evaluation, HITL primitives, taskiq integration, OTel span propagation. Knows nothing about specific workflows. |
| `domain/ticket` (new) | domain | Ticket records, ticket type registry, state machine, persistence. |
| `domain/intake` (new) | domain | The system's coordination layer. Webhook handlers, intake type registry (internal — not pluggable), dedup, ticket creation, **workflow definitions**, ticket-type → workflow routing. |
| `domain/coding_agent` (existing) | domain | Shared Claude Code invocation machinery + cross-task prompt fragments. |
| `domain/reviewer` (existing, evolves) | domain | `CodeReview` WorkflowCommand, `PostFindings` WorkflowCommand. Review-specific finding interpretation. (Workflow definition itself lives in `domain/intake`.) |

**Dependency graph (key edges):**

```
domain/intake ──→ core/workflow         (engine interface)
              ──→ domain/ticket
              ──→ core/workspace        (workspace-lifecycle WorkflowCommands)
              ──→ domain/reviewer       (CodeReview, PostFindings WorkflowCommands)

domain/reviewer ──→ core/workflow        (WorkflowCommand interface)
                ──→ domain/coding_agent  (invocation machinery)
                ──→ core/workspace       (workspace handle for invoke)

core/workspace  ──→ core/agent_gateway

core/workflow   ──→ (taskiq)
core/agent_gateway ──→ (none)
```

Adding a new ticket type later (e.g. investigation): new intake type + new workflow definition in `domain/intake/`, new domain module owning the new WorkflowCommands (e.g. `domain/investigator`), register both with the engine at startup.

### Entities

| Term | Definition | Lifetime | Identity |
|---|---|---|---|
| **Intake** | An inbound signal that creates work. Sources: GitHub PR webhook (M05); future Slack, scheduled scans, user-initiated requests. | Synchronous handler. | Idempotency key derived per intake type. |
| **Ticket** | User-facing unit of work. Persistent. Has a type (`pr_review` for M05), state, payload. The thing a human can point at. | Until terminal (`done`, `failed`, `cancelled`). | UUID + idempotency key. |
| **Workflow** | A typed data structure (definition) describing how a ticket type is processed. Stored in code in `domain/intake/workflows/`. Versioned per definition (`pr_review_v1`). | Definitions are immutable; workflow executions are bound to definition versions. | `<name>_<version>`. |
| **Workflow Execution** | A live instance of a Workflow being driven by the engine for one ticket. Has state, current step, attempt counters, OTel span context. | Created when workflow starts; terminal at `done` / `failed`. | UUID, references ticket + workflow definition. |
| **WorkflowCommand** | A unit of work invoked by the workflow engine as a step. Implementations live in domain modules. Three categories (see below). | One per step execution. | UUID per execution, attempt counter. |
| **AgentCommand** | Wire-protocol primitive from control plane to agent. Single-flight per workspace. Four kinds: `CreateWorkspace`, `InvokeCommand`, `RefreshWorkspaceAuth`, `CleanupWorkspace`. | Seconds to minutes. | UUID + attempt counter. |
| **Workspace** | Isolated sandbox: a dedicated OS process + directory + checked-out code + auth context. Hosts AgentCommands sequentially. | Up to 1h (TTL ceiling matches installation-token lifetime). | UUID. |
| **Agent** | Long-lived Go supervisor process on a customer ECS task. Spawns and routes commands to workspace processes. | As long as the ECS task lives. | Established once via sigv4 → bearer at startup. |

Notes:
- **Instance is not an entity.** The agent represents the host.
- **Workspace bound to its agent for life.** Agent dies → workspace dies. Replacement workspace on a different agent. No migration.
- **Workspace bound to a single workflow execution for M05.** Schema choice (`current_holder_workflow_id` nullable column rather than hard FK) keeps the future relaxation add-only.
- **AgentCommand and WorkflowCommand are different layers, deliberately.** WorkflowCommands compose into workflows; AgentCommands are wire primitives. Some kinds share names across layers (`CreateWorkspace`, `CleanupWorkspace`) because they describe the same operation at different abstractions — disambiguated by layer noun.

### Workflow + WorkflowCommand model

#### Workflow as typed data

A `Workflow` is a typed Pydantic data structure (not ad-hoc code):

| Field | Meaning |
|---|---|
| `name` | Identifier, e.g. `pr_review`. |
| `version` | Integer, incremented on breaking changes. In-flight executions keep using their definition version. |
| `steps` | Ordered list of `Step`. |
| `entry_step_id` | The first step (typically the first in the list). |

Each `Step`:

| Field | Meaning |
|---|---|
| `id` | Identifier unique within the workflow (e.g. `provision`). |
| `command_kind` | The WorkflowCommand kind, e.g. `CreateWorkspace`. |
| `inputs` | Mapping from input names to source expressions (`$ticket.repo`, `$provision.workspace_id`, `$mint_install_token`). |
| `retry_policy` | Bounded attempts + backoff. |
| `hitl` | If true, step pauses workflow until external resume signal. |
| `transitions` | Map from outcome label → next step ID, or terminal action (`fail_workflow`, `complete_workflow`). Default: `success → <next listed step>`, `failure → fail_workflow`. |

#### The three WorkflowCommand categories

| Category | What it does | Examples (M05 + near-future) | Implementation home |
|---|---|---|---|
| **Workspace** | Operates on a workspace. Issues AgentCommands under the hood. | `CreateWorkspace`, `CleanupWorkspace`, `RefreshWorkspaceAuth` (lifecycle); `CodeReview`, `Investigate`, `Implement` (work) | `core/workspace` owns lifecycle ones; task-type domain modules own work ones. |
| **Local** | Runs in the backend process. No workspace. | `PostFindings` (to GitHub via VCS), future `NotifyUser`, `RecordAudit` | Whatever domain module owns the concern. |
| **HITL** | Suspends workflow until a human resolves it. | Future `RequestApproval`, `AwaitClarification` | `core/workflow` provides the primitive; domain modules instantiate. |

#### WorkflowCommand interface

A WorkflowCommand implementation declares:

- `kind` (string).
- `restart_safe` (boolean — see restart-safety section).
- `inputs_schema` (Pydantic model — what it expects).
- `outputs_schema` (Pydantic model — what it returns; available as `$<step_id>.<field>` to later steps).
- `execute(inputs, context) -> Outcome` where `Outcome` is one of: success with outputs, failure with reason, hitl-pending with question payload. The implementation may also return `append_steps=[...]` (see escape hatch).

#### Engine state machine

`WorkflowExecution` row tracks:

- `id`, `workflow_name`, `workflow_version`, `ticket_id`.
- `state`: one of `pending`, `running`, `awaiting_human`, `done`, `failed`.
- `current_step_id`.
- `step_state`: per-step attempt counters + last outcome + outputs (kept for input resolution in later steps).
- `otel_trace_context` (serialized W3C traceparent + tracestate).
- `created_at`, `updated_at`.

State transitions:

```
pending ──start──→ running ──step success──→ running (next step)
                          ──step failure (retries exhausted)──→ apply on_failure
                                                              → running | failed
                          ──hitl pending──→ awaiting_human
                          ──terminal action──→ done | failed

awaiting_human ──resume signal──→ running
```

#### HITL pattern — how it actually works

1. Workflow reaches a step with `hitl: true`. Step implementation writes a row to a `pending_human_decisions` table (`workflow_execution_id`, `question_payload`, `created_at`).
2. Engine marks workflow `awaiting_human`. **Does not enqueue the next step.** No taskiq task pending.
3. Workflow is dormant. No resource burn beyond a row in two tables.
4. Human visits UI, sees the decision, submits a response.
5. UI handler writes resolution to the decision row, transitions workflow to `running`, looks up the step's `transitions` map keyed on the user's response, enqueues the next step via taskiq with that response as input.
6. Workflow resumes.

No taskiq feature needed beyond "enqueue this task." HITL is a workflow state, not a long-running task.

#### Dynamic step insertion (append-steps escape hatch)

A WorkflowCommand implementation can return `append_steps=[Step, Step, ...]` along with its outcome. The engine inserts those steps at the front of the remaining sequence before evaluating the next transition.

Used for: cases where a static workflow definition is the prefix, and what comes next is determined by what's discovered. Example future use: an `Investigate` step's findings determine how many `Plan` and `Implement` sub-steps follow.

For M05 the PR review workflow does not use this mechanism, but the engine supports it.

#### Three-tier retry separation

Retries happen at three levels, with clean responsibilities:

| Tier | Where | Triggered by | Action |
|---|---|---|---|
| **1. AgentCommand recovery** | `core/workspace` | Workspace process / agent reports a failure event. | Apply recovery policy (e.g. `auth_expired` → issue `RefreshWorkspaceAuth` AgentCommand; retry original). If recovery fails, dispose workspace + provision new + re-dispatch original WorkflowCommand. Bounded. From the engine's view this is still one WorkflowCommand execution in flight. |
| **2. WorkflowCommand step retry** | `core/workflow` engine | WorkflowCommand returns failure (after AgentCommand-level recovery exhausted). | Per `step.retry_policy` (default: 1 attempt). On exhaustion, evaluate `step.transitions[failure]`. |
| **3. Workflow-level transition** | `core/workflow` engine | Step's failure transition. | Route to next step, skip, fail workflow, or terminal action. Workflow failure → ticket marked `failed`. |

Ticket-level retry (re-running the workflow itself) is a future concern, not M05.

### Engine implementation — taskiq is just a task scheduler

The `core/workflow` engine owns the state machine. Taskiq is used purely as a durable, retry-capable single-task scheduler.

| Layer | Owns |
|---|---|
| `core/workflow` engine | Workflow state machine, transitions (static + dynamic), HITL gating, retry decisions, span propagation, ticket-state synchronization. |
| taskiq | "Run this function once, with bounded retry, durably across backend restarts." |

Each step execution is one taskiq task. Task body (pseudo-flow):

1. Load `WorkflowExecution` from DB.
2. Restore OTel span context.
3. Open a child span for this step.
4. Look up `Step` and `WorkflowCommand` by kind.
5. Resolve inputs from `step_state` + ticket payload.
6. Execute the WorkflowCommand.
7. Record outcome in `step_state`.
8. If `append_steps` returned, insert.
9. Evaluate `transitions` map. If next step → enqueue taskiq task for it. If HITL → mark `awaiting_human`, do nothing. If terminal → mark workflow `done` / `failed`, mark ticket terminal.
10. Close span.

We don't use taskiq's pipelining, chains, result backend, or dependency graph. This means the engine's logic is portable — if taskiq stops fitting (durable execution complexity blows up), we can swap to Celery/RQ/Temporal with the same shape.

### Workspace provider contract is uniform

The `WorkspaceProvider` interface in `core/workspace` is the boundary. Two implementations:

| Provider | What it does | When used |
|---|---|---|
| `InMemoryWorkspaceProvider` (existing, evolves) | Spawns workspaces as in-process constructs (subprocess inside the backend container). Implements the **exact same protocol** — same AgentCommands, same lifecycle, same single-flight, same recovery policy, same failure-report-precedes-disposal invariant. | Dev, E2E tests, single-tenant self-hosted (future). |
| `RemoteAgentWorkspaceProvider` (new in M05) | Dispatches via `core/agent_gateway` to a customer-deployed agent. | Production, multi-tenant. |

Per-org config in org settings: `workspace_provider: in_memory | remote_agent`.

**The in-memory provider does not get a free pass.** It enforces all invariants — even single-flight (trivially enforceable in-process, but the enforcement code path exists, gets tested, and proves the contract is real). Cleanup failsafes apply. Failure-report-precedes-disposal applies. Recovery policy applies.

Implication: E2E tests can use `in_memory` and validate every rule, because the rules live above the provider. Eventually in prod the `in_memory` option gets disabled at the org-settings allowlist level. We don't delete the implementation — it's too useful for E2E.

### Agent process model (the remote agent only)

OS-process isolation, not goroutines.

- **Supervisor process** (`agent supervisor` subcommand): one per ECS task. Holds the only network connection to yaaof. Runs long-poll workers, spawns/kills workspace processes, routes commands, forwards events, heartbeats, runs disk janitor + reconciliation.
- **Workspace process** (`agent workspace --id <uuid>` subcommand of the same binary): one per active workspace. Spawned by the supervisor via `os/exec` on `CreateWorkspace`; killed on `CleanupWorkspace`. Owns its workspace directory. Spawns Claude Code, git, tests as its children — when the workspace process dies, all its children die.

**IPC:** pipes between supervisor and workspace process. Commands written as JSON-newline to the workspace's stdin; events read as JSON-newline from stdout. stderr captured for supervisor-local logs.

**Why OS processes:**
- Real memory + CPU isolation; one workspace's subprocess can't reach into another's heap.
- Crash isolation; a segfault in a workspace doesn't kill the supervisor.
- Foundation for future per-workspace sandboxing (landlock, seccomp, network namespaces, per-workspace UID) without rearchitecting.
- The supervisor stays small and stable; volatile code paths live in disposable processes.

**Provisioning cost:** spawning a workspace process adds ~1s vs. a goroutine. Acceptable; workspaces live for minutes and the isolation gain is large.

### Three liveness signals

Distinct on purpose. Never conflated.

| Signal | What it asserts | Source | Cadence | Failure action |
|---|---|---|---|---|
| **Agent liveness** | Supervisor up, network reachable, can accept commands. | Supervisor → `POST /v1/agents/{id}/heartbeat`. Includes inventory of workspaces it currently owns (reconciliation channel). | 30s | Silent > 90s → all its workspaces marked `agent_unreachable`; in-flight AgentCommands fail with `agent_lost`. |
| **Workspace health** | Workspace process alive, in known state, ready for AgentCommands. | Per-workspace status field carried inside the agent heartbeat inventory. | Implicit. | Failure → cleanup + re-provision (per disposable-workspaces rule). |
| **AgentCommand progress** | This AgentCommand hasn't hung. | Status events from the workspace process on state changes; wall-clock timeout in AgentCommand payload. | No per-command heartbeat in POC. | Wall-clock exceeded → supervisor kills workspace process; emits `command_timeout`. |

### Zero biz logic in the agent

The agent (supervisor + workspace processes) contains **no business logic**. Every threshold, history depth, timeout, lesson, prompt, retry limit, recovery decision is supplied by the control plane in the AgentCommand payload. The agent does:

- HTTP client + identity refresh (supervisor)
- Process supervision (supervisor)
- Filesystem ops, git, subprocess management (workspace process)
- Event reporting (both)

Compiled-in safety floors only reject obvious garbage (e.g. `max_wall_seconds > 86400`). Anything that looks like a heuristic, default, or policy is a smell — push it to the payload.

### Workspace lifecycle

```
requested → provisioning → ready ⇄ busy → terminating → gone
                ↓             ↓        ↓
              (failed) ──→ cleanup (best-effort) ──→ gone
```

- `gone` is the only terminal state.
- No `degraded` state. Failure goes straight through cleanup to `gone`.
- An AgentCommand transitions a workspace `ready → busy → ready`. Single-flight; many AgentCommands per workspace sequentially.
- Any non-terminal state can carry an `agent_unreachable` flag (transient). Past a threshold → `orphaned` (terminal, equivalent to `gone` for accounting).

### Single-flight per workspace

At most one AgentCommand in flight per workspace at any moment. Enforced in two places.

**Control plane (primary).** Workspace row has a nullable `current_command_id` column. Dispatch to workspace `W` is an atomic claim:

> `UPDATE workspaces SET current_command_id = $cmd WHERE id = $W AND current_command_id IS NULL` — zero rows updated means another dispatcher won; don't send.

Terminal event from the agent clears the field. **No separate commands table** in M05 — AgentCommands are ephemeral, live in `core/agent_gateway`'s in-memory per-agent queue. Backend restart drops in-flight commands; reconciliation via the next heartbeat rebuilds state.

**Agent (defense in depth).** The supervisor maps `workspace_id → workspace_process`. Each workspace process has one command pipe and processes one command at a time by construction. If a second command somehow arrives for an already-busy workspace, the supervisor emits a `workspace_busy` event and drops the command. Control plane reconciles.

### Workspace-to-workflow binding (M05)

A workspace is bound to exactly one workflow execution for its lifetime. Never shared across tickets, never shared across workflows.

Schema choice that keeps future relaxation add-only: workspaces table has a nullable `current_holder_workflow_id` column (not a hard FK). M05 invariant: this is set at workspace creation and cleared on cleanup, equal to the creating workflow execution's lifetime. Future relaxation (workspace reuse across workflows on the same PR): nullable when a workflow releases-but-doesn't-cleanup; provisioning policy can claim an unheld workspace by setting the field. Schema doesn't change; only the population pattern does.

### Disposable workspaces + recovery

Workspaces are disposable. Any unexpected failure → cleanup → new workspace.

**But the control plane tries to save first.** Each failure event carries a `reason` enum. `core/workspace` has a policy mapping reason → recovery AgentCommand, applied before dispose-and-replace.

Initial policy (will grow as real failure modes appear):

| Reason | Recovery |
|---|---|
| `auth_expired` | Issue `RefreshWorkspaceAuth` to the workspace; retry original AgentCommand. |
| everything else | Dispose + provision new workspace + re-dispatch. |

Recovery attempts and outcomes are audit-logged. From the workflow engine's perspective, recovery is internal to one WorkflowCommand execution.

### Cleanup failsafes (belt-and-suspenders)

1. **Idempotent cleanup commands.** Re-delivery is a no-op once workspace is `gone`.
2. **TTL.** Every workspace carries `expires_at ≤ created_at + 1h`. Agent unconditionally cleans up past expiry.
3. **Idle timeout.** Workspace carries `max_idle_seconds`. Agent cleans up after that much idle.
4. **Startup reconciliation.** Supervisor boots → inventories `/var/agent/workspaces/`, reports in first heartbeat. Control plane returns "delete these" for any it doesn't recognize.
5. **Disk sweep.** Slow background pass in the supervisor: any directory whose UUID isn't in the in-memory workspace table → force delete.
6. **Agent-loss recovery.** Control plane marks unreachable agents' workspaces `orphaned` after threshold. If the agent comes back it gets cleanup commands. If not, Fargate eventually reclaims storage.
7. **Audit trail.** Every workspace state transition writes an audit row.

### Invariant: failure report precedes disposal

Before any workspace disposal — `CleanupWorkspace`, TTL/idle, crash-handler, recovery-driven — a terminal event must be emitted capturing failure reason, subprocess exit codes, last error message, and tail of the workspace process's internal log. Best-effort: if the control plane is unreachable, the event is queued for retry and disposal proceeds anyway (debuggability falls back to supervisor-local logs).

### Protocol shape (AgentCommands)

Five endpoints. Single outbound TLS connection from the supervisor. All paths under `/v1/`.

| Endpoint | Purpose |
|---|---|
| `POST /v1/identity/exchange` | sigv4-signed STS request → short-lived bearer (Vault AWS auth pattern). |
| `POST /v1/agents/{id}/heartbeat` | Supervisor liveness + workspace inventory (reconciliation). |
| `POST /v1/agents/{id}/commands/claim` | Long-poll (~30s, max 55s) → returns one AgentCommand at a time. |
| `POST /v1/workspaces/{id}/events` | Workspace state transitions; scoped to a `command_id` for ack. |
| `POST /v1/commands/{id}/events` | AgentCommand progress + terminal result. |

**AgentCommand kinds:**

- `CreateWorkspace(workspace_id, repo, history, auth, ttl, max_idle, traceparent)` — supervisor spawns a new workspace process.
- `RefreshWorkspaceAuth(workspace_id, new_token, traceparent)` — rotates the installation token inside an existing workspace process.
- `InvokeCommand(workspace_id, command_id, invocation, lessons, limits, result_spec, traceparent)` — runs Claude Code (or other coding agent) against the workspace.
- `CleanupWorkspace(workspace_id, traceparent)` — supervisor terminates the workspace process and removes its directory.

Every AgentCommand and AgentEvent carries `traceparent` (W3C trace context) so spans nest correctly across the wire.

**Concurrency:** default 4 workspaces per agent. Configurable up to ~10–20 on larger ECS task sizes. Each free slot in the supervisor issues its own long-poll. ECS service auto-scales tasks above sustained load.

**Stale-claim guard:** event endpoints return `410 Gone` when the agent's `command_id`/`attempt` doesn't match current control-plane state. Agent abandons silently.

### Per-AgentCommand restart safety

| AgentCommand | Restart-safe? | Notes |
|---|---|---|
| `CreateWorkspace` | yes | New workspace ID per retry; no observable leak on retry of a failed create. |
| `RefreshWorkspaceAuth` | yes | Rotates the in-memory token in the workspace process; idempotent. |
| `InvokeCommand` | yes (at user-visible level) | Re-running a review regenerates findings; control plane posts findings idempotently by external_id, so duplicates don't surface in VCS. |
| `CleanupWorkspace` | yes | Re-delivery is a no-op once `gone`. |

Future AgentCommands (e.g. anything with VCS-write side effects) must declare this property when added.

### Secrets handling

Different processes hold different secrets. The supervisor is the trusted shell; the workspace process is the disposable executor.

| Credential | Supervisor has? | Workspace process has? | Source | Scope |
|---|---|---|---|---|
| Yaaof control plane bearer | yes (in memory, refreshed proactively) | **no** | Identity exchange | All `/v1/...` endpoints |
| GitHub installation token | yes (forwards to workspace) | yes (env at spawn) | Minted by control plane per workspace | Single repo, ~1h |
| Anthropic API key (BYOK) | yes (inherits from ECS env) | yes (forwarded to Claude Code via env) | Customer Secrets Manager → ECS env | LLM API only |
| MCP proxy credentials (M04) | yes (in AgentCommand payload) | yes (in Claude Code MCP config) | Control plane in `InvokeCommand` payload | Tool access via M04 proxy |

**Critical property:** the workspace process has no credentials for the yaaof control plane API. Findings cross the trust boundary only through the supervisor, which is the audited piece.

**Logging discipline:** secrets wrapped in a redacting type from day one; subprocess command lines and env vars never logged verbatim.

### Trust boundary — what crosses, what doesn't

- **Crosses into yaaof:** findings, structured supervisor telemetry, workspace + AgentCommand state events, OTel spans.
- **Stays in customer VPC:** all source code, all diffs, all subprocess stdout/stderr (Claude Code, git, tests). Subprocess output may eventually ship to the customer's own observability stack (configured separately) but never to yaaof.
- **Crosses to the M04 MCP proxy (not yaaof):** tool-call traffic from Claude Code in workspace processes.

### Tracing (OpenTelemetry)

End-to-end distributed tracing from webhook arrival to GitHub comment posted. One trace ID covers the entire journey.

**Span hierarchy:**

- **Workflow execution span** — created when `core/workflow.start()` is called. Attributes: `workflow.name`, `workflow.version`, `ticket.id`, `ticket.type`. Spans the entire workflow including HITL waits.
- **WorkflowCommand step span** — child of the workflow span. One per step execution (including retries). Attributes: `step.id`, `step.kind`, `step.attempt`, `step.outcome`.
- **AgentCommand span** — child of the step span (when the WorkflowCommand issues one). Attributes: `agent_command.kind`, `agent_command.id`, `workspace.id`, `agent.id`.
- **Wire spans** — propagated via `traceparent` header (and `traceparent` field in payloads). Agent supervisor creates spans for claim, dispatch, event-forward. Workspace process creates spans for clone, invocation, subprocess.
- **Subprocess spans** — workspace process exports `TRACEPARENT` / `TRACESTATE` env to Claude Code; if subprocess emits OTel it nests correctly. Otherwise the workspace-process span covers it.

**Cross-process propagation:**
- Backend → agent: `traceparent` in AgentCommand payload.
- Supervisor → workspace process: `TRACEPARENT` / `TRACESTATE` in env at spawn.
- Workspace process → Claude Code subprocess: same env vars.

**Persistence of trace context:**
- `WorkflowExecution.otel_trace_context` field stores serialized W3C trace context. Survives backend restarts. Restored when a taskiq task picks up the next step.

OTel is assumed available in the backend per CLAUDE.md observability-hooks discipline. If not yet wired, that's a parallel prerequisite.

### Heartbeat / reclaim defaults (POC)

- Supervisor heartbeat: 30s cadence, 90s reclaim threshold (3 misses).
- All values payload/config controlled — these are defaults, not constants.

### End-to-end PR review flow (concrete)

The M05 reference flow. Used to validate every layer of the design.

1. **Webhook arrives** at `domain/intake/handlers/github_pr`. Signature verified, payload validated, idempotency key derived (`github:<repo>:<pr>:<event_id>`).
2. **Ticket created.** `domain/ticket.create(type=pr_review, payload={repo, pr_number, base_ref, head_ref, installation_id}, idempotency_key=...)`. Returns `ticket_id`.
3. **Workflow started.** `core/workflow.start(workflow_name=pr_review, version=1, ticket_id=...)`. Creates `WorkflowExecution`, opens a new OTel span (workflow.id, ticket.id as attributes), enqueues step 1's taskiq task.
4. **Webhook returns 200** with `{ticket_id}`. Synchronous.
5. **Step 1: `CreateWorkspace`** WorkflowCommand executes (in `core/workspace`). Opens child span. Calls configured `WorkspaceProvider` (in_memory or remote_agent based on org settings). Provider dispatches `AgentCommand: CreateWorkspace` (wire) → agent → workspace process spawned → cloned → `ready` event. Workflow execution records workspace_id in step outputs.
6. **Step 2: `CodeReview`** WorkflowCommand executes (in `domain/reviewer`). Opens child span. Imports invocation machinery from `domain/coding_agent`. Assembles AgentCommand payload (directive, lessons, MCP server configs, limits, result spec, traceparent). Calls `core/workspace.invoke(workspace_id, payload)`. Provider dispatches `AgentCommand: InvokeCommand` (wire) → agent → workspace process runs Claude Code → findings returned via event.
7. **Step 3: `PostFindings`** WorkflowCommand executes (in `domain/reviewer`). Opens child span. Calls existing VCS module to post comments to GitHub, idempotent by `external_id`.
8. **Step 4: `CleanupWorkspace`** WorkflowCommand executes (in `core/workspace`). Opens child span. Provider dispatches `AgentCommand: CleanupWorkspace` (wire) → agent terminates workspace process → directory removed → `gone` event.
9. **Workflow done.** Engine marks execution `done`, closes workflow span, marks ticket `done`.

The `pr_review_v1` workflow definition lives at `domain/intake/workflows/pr_review.py`. The PR review run is, end to end, ~15 lines of declarative data plus the implementations of the four WorkflowCommands.

## Open questions / TBD

In rough dependency order.

### Protocol details

- **TBD: full OpenAPI schemas.** Concrete request/response shapes for all five endpoints, AgentCommand discriminated union, AgentEvent schemas, traceparent fields, error envelopes.
- **TBD: AgentCommand acknowledgement model.** Does the agent ack a command synchronously on receipt and then send completion events, or does each command have one terminal event that doubles as ack?
- **TBD: idempotency keys.** Sketched as `(command_id, attempt)`. Confirm against reclaim semantics.
- **TBD: findings schema.** Deferred to implementation alongside the reviewer module that consumes them.

### Agent internals

- **TBD: Claude Code invocation details.** Headless mode flags, how the directive is passed (stdin, `--print`, prompt file), where lessons live on disk during the run, MCP server configuration mechanism, how structured output comes back.
- **TBD: workspace filesystem layout.** Path conventions, per-workspace UID strategy (single shared UID for POC vs. per-workspace), where Claude Code config lives within the workspace.
- **TBD: subprocess sandboxing layered on top of OS-process isolation.** Landlock, seccomp, network namespaces, per-workspace UID. POC ships OS-process isolation only.
- **TBD: workspace process IPC framing.** Pipe + JSON-newline is the plan; need to nail message envelope, error framing, backpressure.
- **TBD: workspace orphan handling.** Should the workspace process self-shutdown if the supervisor pipe closes? (Probably yes — pipe-close as a death signal.)

### Control plane changes

- **TBD: existing `core_workspace` integration.** How the new model layers onto the existing `WorkspaceProvider` contract — extension or restructuring. Decide when reading existing code.
- **TBD: existing `domain/reviewer` reshape.** What stays, what moves into WorkflowCommands, what's deleted. Decide when reading existing code.
- **TBD: existing `review_job` → ticket migration.** Confirmed direction (review_job becomes `pr_review` ticket type + `CodeReview` AgentCommand); migration mechanics TBD.
- **TBD: provisioning policy.** "Which agent gets the next workspace?" Initial: least-loaded among reachable agents. Refine over time.
- **TBD: recovery policy table growth.** Initial table is single-row (`auth_expired`). Grow as we observe real failure modes.
- **TBD: reconciliation algorithm.** Concrete logic for comparing expected vs. reported workspace inventory and resolving drift.
- **TBD: HITL UI surface.** Where users see pending decisions and respond. Not exercised in M05 (no HITL workflows) but the data model needs to land.

### Identity + secrets

- **TBD: AWS sigv4 verification flow on yaaof's side.** Library choice, signature replay semantics, registration of customer ARNs.
- **TBD: installation token rotation cadence.** When does the control plane preemptively refresh tokens? On dispatch, or on a schedule?
- **TBD: secrets redaction implementation.** Concrete `secret.String` type for Go; logging hook that scrubs known-secret field names.

### Operations

- **TBD: agent image release process.** Where the image is published (public ECR vs. Docker Hub), tagging strategy, customer notification of new versions.
- **TBD: local dev story.** How developers run the supervisor + workspace processes against a local backend without AWS. Likely docker-compose with an STS-bypass dev-mode identity exchange. Also: `in_memory` provider as the primary local-dev path.
- **TBD: e2e test story.** How `apps/e2e/` exercises a flow that goes intake → workflow → workspace → Claude Code → back. The `in_memory` provider should make this straightforward.
- **TBD: observability beyond tracing.** Structured log field set, metric set (claim rate, command latency, workspace count, workflow duration histograms, step retry counts).
- **TBD: existing in-process workspace provider's coexistence.** It must obey the same contract (locked above). Implementation TBD when reading existing code.

### Failure-mode coverage

- **TBD: supervisor crash mid-cleanup.** Failsafe list covers it (disk sweep + reconciliation) but walk through the exact sequence.
- **TBD: network partition.** Concrete rules for when the supervisor gives up an in-flight AgentCommand and stops doing work whose results it can't deliver.
- **TBD: disk-full / OOM.** What the supervisor reports and how it recovers.
- **TBD: taskiq broker outage.** What happens to in-flight workflows when the Postgres broker is unreachable. Engine should degrade gracefully (workflows pause, resume when broker is back).

### Strategic gaps to fill in future iterations

These deserve their own design passes before M05 ships, but are deferred from the current round so we can focus.

- **TBD: image + protocol versioning.** Customer agents will drift in version. Compatibility policy: does a new control-plane endpoint break old agents? Does an old agent connecting refuse to register? Release cadence + deprecation policy. The `agent_version` field in identity exchange is the hook; semantics TBD.
- **TBD: multi-tenancy + fairness.** Control plane dispatches across N customers. One customer drops 50 PRs at once — does that block another customer's single PR? Per-customer queue / capacity / SLA. Likely needs per-org concurrency caps + fair scheduling.
- **TBD: customer-side observability + audit.** What the customer sees about their own agent's activity. Their security/compliance teams will ask. Currently the agent emits structured logs locally; how is that surfaced — only via their own observability stack, or also via the yaaof control-plane UI? Audit log access for customer admins.
- **TBD: MCP proxy interaction details.** We name-check the M04 MCP proxy but haven't mapped: where it runs (yaaof-hosted vs. customer-hosted), how the workspace process authenticates to it, what tools it exposes, latency considerations, what credential surface it adds.

### Optimizations (deferred until measured)

- **Git worktree cache.** Single bare clone per `(customer, repo)` with per-workspace worktrees. Right primitive identified; adds complexity (object DB lock contention, submodules, LFS). Add when first customer has a large monorepo. Shallow clone is fast enough for POC.
- **Workspace reuse across workflow executions on the same PR.** Currently locked to single-use per workflow execution. Schema (`current_holder_workflow_id` nullable) makes the future relaxation add-only — release-but-don't-cleanup pattern + provisioning-policy reuse rule. Add when measurement shows clone time is the bottleneck or customer experience demands ~instant follow-up reviews.
- **Per-workspace network egress restrictions.** Currently no constraint. Future: restrict workspace process egress to allowed hosts (Anthropic API, customer's VCS host, MCP proxy). Customer-side concern; needs a story.

## Non-goals for M05

- **Workspace migration between agents.** Bound for life; replacement on agent loss.
- **Workflow engine swap.** Architecture supports portable workflow definitions; we use taskiq for now.
- **Multi-provider LLM support.** Anthropic only.
- **Multi-VCS support.** GitHub only.
- **Per-process sandbox hardening beyond OS-process isolation.** Landlock/user-ns post-POC.
- **Git worktree cache.** Premature until clone time is measured.
- **Workspace reuse across workflow executions.** Locked single-use; relaxation is post-M05.
- **Multi-command workflows / HITL.** Engine supports them; M05 only ships a 4-step linear PR review workflow.
- **Ticket-level retry policies.** Workflow-level retry covers M05 needs.

## Reading list (when we resume — implementation planning)

1. `apps/backend/docs/core_workspace.md` and existing `WorkspaceProvider` code — decides extension strategy for `core/workspace`.
2. Existing `domain/reviewer` code — decides what becomes WorkflowCommands and what stays.
3. Existing `domain/coding_agent` code — confirms shared-invocation responsibilities.
4. `plan/notes/security-posture.md` — predecessor strategy doc; reconcile.
5. Existing audit-log shape (`docs/system-architecture.md`) — workspace + AgentCommand + workflow events must fit.
6. M04 MCP proxy docs — how workspace processes connect for tool access.
7. Current OTel setup in the backend (if any) — confirms tracing infrastructure availability.

## Verification (when shipped — not now)

To be expanded when the milestone is closer to ready. Will include:

- E2E test exercising the full PR review flow (intake → workflow → workspace → Claude Code → GitHub post → cleanup) using the `in_memory` provider.
- E2E test of the same flow against `remote_agent` provider with a real (or stubbed) agent.
- Identity exchange path tested against AWS STS in CI (or stubbed STS for dev).
- All cleanup failsafes tested via fault injection.
- Recovery policy applied for the `auth_expired` path (token forced to expire mid-AgentCommand).
- Workspace process crash → supervisor emits failure event → control plane provisions replacement.
- HITL primitive smoke test (even though no M05 workflow uses it — exercises the engine path).
- Trace assertion: one trace ID covers webhook → comment posted, with nested spans for each step + each AgentCommand.
- `in_memory` provider obeys all the same invariants as `remote_agent` (single-flight, recovery, failure-report-precedes-disposal).
