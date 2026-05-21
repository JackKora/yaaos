# M05 — Workspace Agent

> Customer-deployed worker that hosts isolated workspaces and runs coding agents (Claude Code today; others later) against customer code, on customer infrastructure. Plus a generalized Workflow + WorkflowCommand model in the control plane that subsumes today's `review_job` and supports future investigation / planning / implementation / HITL workflows.

**Status:** [in progress] — strategic design captured; many implementation details TBD.

## Reading order

1. [requirements.md](requirements.md) — locked decisions and open questions. Covers the module map, entity model, Workflow + WorkflowCommand model, agent process architecture, lifecycle, single-flight, disposable + recovery, protocol, secrets, tracing, end-to-end flow, and TBDs.

(More docs — `architecture.md`, OpenAPI spec, deployment runbook — added as the milestone matures.)

## What's locked

### Architecture

- **Two new core modules:** `core/agent_gateway` (wire protocol), `core/workflow` (engine mechanics — taskiq as just a task scheduler).
- **Two new domain modules:** `domain/ticket`, `domain/intake` (webhooks + intake types + workflow definitions + routing).
- **Existing modules evolve:** `core/workspace`, `domain/coding_agent`, `domain/reviewer`.

### Concepts

- **Entity model:** Intake → Ticket → Workflow Execution → WorkflowCommand → AgentCommand → Workspace. Agent represents the host (no Instance entity).
- **Two command layers, deliberately distinct:** `WorkflowCommand` (engine-level, three categories — Workspace / Local / HITL) and `AgentCommand` (wire-protocol, four kinds).
- **Workflows are typed data structures** with steps, transitions, retry policies, HITL flags, and an append-steps escape hatch. Workflow definitions live in `domain/intake/workflows/`.
- **Three-tier retry separation:** AgentCommand recovery (in `core/workspace`) → WorkflowCommand step retry (engine) → workflow-level transition (engine).
- **Three distinct liveness signals:** agent / workspace / AgentCommand. Not conflated.
- **Three OTel span layers:** workflow execution → step → AgentCommand (with wire propagation via `traceparent`).

### Agent

- **Language:** Go. **Deployment:** public Docker image; customer runs in ECS/Fargate.
- **Process model:** supervisor process + one OS process per workspace, IPC over pipes.
- **Zero biz logic in the agent.** Every threshold, prompt, lesson, depth, timeout supplied by control plane.

### Workspaces

- **Bound to their agent for life** (no migration in POC). TTL ≤ 1h.
- **Bound to exactly one workflow execution for M05.** Schema (`current_holder_workflow_id` nullable) keeps future reuse relaxation add-only.
- **Disposable with recovery-first policy** — control plane tries known fixes (e.g. `RefreshWorkspaceAuth`) before dispose-and-replace.
- **Single-flight per workspace** — enforced in control plane (atomic claim on `current_command_id`) and in agent (one command pipe per workspace process).
- **Failure report precedes disposal** — invariant.

### Protocol

- **Long-poll HTTPS, single egress, sigv4-based identity exchange** (Vault AWS auth pattern).
- **Five endpoints, four AgentCommand kinds.** `traceparent` on every AgentCommand and AgentEvent.
- **Trust boundary:** source code never leaves customer VPC; only findings + structured supervisor telemetry + spans cross. Workspace processes have no yaaof control plane credentials.

### Provider contract

- **`WorkspaceProvider` is uniform.** `InMemoryWorkspaceProvider` (existing, for dev / E2E) and `RemoteAgentWorkspaceProvider` (new, for prod) implement the same protocol, enforce the same invariants.
- **Per-org configurable** via org settings: `workspace_provider: in_memory | remote_agent`.

## What's not yet decided

See the "Open questions / TBD" section in [requirements.md](requirements.md) — covers protocol schemas, agent internals, control-plane refactor specifics, identity flow, operations, failure-mode coverage, and four strategic gaps deferred from this round (image + protocol versioning, multi-tenancy + fairness, customer-side observability + audit, MCP proxy interaction details).
