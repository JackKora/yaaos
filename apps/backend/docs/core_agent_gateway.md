# core/agent_gateway

> Wire protocol to customer-deployed WorkspaceAgents.

## Purpose

The only module that talks to remote WorkspaceAgents. Owns the long-poll HTTPS endpoints (`/v1/agents/...`) and the activity-stream WebSocket, the per-agent in-memory dispatch queue, identity exchange via SigV4-signed STS replay, heartbeat ingestion, and AgentEvent routing back into [`core/workflow`](core_workflow.md). Phase 0b ships an empty skeleton — Phases 5 + 8b implement the protocol.

## Public interface

Empty in Phase 0b. Phase 5 adds the long-poll handlers + dispatch API consumed by `RemoteAgentWorkspaceProvider`. Phase 8b adds the WebSocket activity stream.

## Module architecture

Phase 5+. See [plan/milestones/M05-workspace-agent/architecture.md § Protocol shape](../../../plan/milestones/M05-workspace-agent/architecture.md#protocol-shape-agentcommands) and [`apps/backend/openapi/agent-api.yaml`](../openapi/agent-api.yaml).

## Data owned

Phase 5+. Will own `workspace_agents`.

## How it's tested

Phase 5 adds: long-poll 204/200, heartbeat reconciliation, event routing, stale-claim `410 Gone`. Phase 8b adds: activity stream end-to-end against both providers, demand-pull, WebSocket reconnect, trust-boundary.
