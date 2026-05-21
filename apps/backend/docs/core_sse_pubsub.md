# core/sse_pubsub

> Redis pub/sub wrapper for ActivityEvent fanout to SSE subscribers.

## Purpose

Thin wrapper over Redis pub/sub. [`core/agent_gateway`](core_agent_gateway.md) publishes ActivityEvents to `activity:{workflow_execution_id}`; the SSE handler in `core/webserver` subscribes per workflow execution and streams to the UI. Phase 0b ships an empty skeleton — Phase 8b wires the full demand-pull subscription protocol.

## Public interface

Empty in Phase 0b. Phase 8b adds: `publish(channel, event)`, `subscribe(channel) -> AsyncIterator`.

## Module architecture

Phase 8b+. Channel name shape: `activity:{workflow_execution_id}`. Subscriber counts drive the agent-side demand-pull — when an SSE handler is the first subscriber for a workflow, the WorkspaceAgent is told to start streaming activity; when the last subscriber drops, streaming stops.

## Data owned

None. Redis is ephemeral transport; [`core/audit_log`](core_audit_log.md) remains the durable record.

## How it's tested

Phase 8b adds: activity stream end-to-end against both providers, demand-pull (no events without subscriber), trust-boundary (no source content in ActivityEvent payloads).
