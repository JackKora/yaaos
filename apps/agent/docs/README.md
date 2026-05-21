# apps/agent — yaaos WorkspaceAgent

> Customer-deployed Go binary that holds customer source code, runs coding agents locally, and reports findings + telemetry back to the yaaos control plane.

## Phase

M05 Phase 0b — skeleton. `cmd/agent/main.go` dispatches to `supervisor` or `workspace` subcommands; both return "not implemented" until Phase 6.

## Architecture

The agent is **zero biz logic** — every threshold, prompt, lesson, depth, and timeout comes from the control plane via AgentCommand payload. The agent is OS-process scheduling + IPC framing + repo clone + Claude Code subprocess management. No policy.

### Subcommands

- `agent supervisor` — long-poll the control plane's `core/agent_gateway`, spawn one OS process per active workspace, heartbeat back inventory + liveness, run the disk janitor. (Phase 6.)
- `agent workspace` — per-workspace child process; reads AgentCommands over stdin, writes AgentEvents over stdout. Wraps git clone + Claude Code CLI. (Phase 6.)

### Layout

- `cmd/agent/` — main entrypoint, subcommand dispatch.
- `internal/supervisor/` — supervisor loop, long-poll workers, heartbeat, janitor.
- `internal/workspace/` — workspace process body.
- `internal/ipc/` — JSON-newline framing for supervisor↔workspace pipes.
- `internal/identity/` — SigV4-signed STS `GetCallerIdentity` for control-plane verification.
- `bin/ci` — `go vet ./... && go build ./...`. Phase 6 adds test runs.

## Wire protocol

See [`apps/backend/openapi/agent-api.yaml`](../../backend/openapi/agent-api.yaml). Hand-written OpenAPI; backend Pydantic + Go types both regenerate from this file.

## Phase boundaries

- **Phase 0b (this)** — directory + go.mod + skeleton package files + `bin/ci`.
- **Phase 5** — backend's `core/agent_gateway` implements the long-poll endpoints + STS verifier.
- **Phase 6** — supervisor + workspace bodies, IPC framing, identity exchange.
- **Phase 9** — Dockerfile, image registry, deployment guide.
