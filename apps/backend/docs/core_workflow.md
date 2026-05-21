# core/workflow

> Workflow engine — typed workflows, three command categories, async event-driven execution.

## Purpose

Owns `Workflow`, `Step`, `WorkflowCommand`, `Outcome`, and the three [`core/tasks`](core_tasks.md) task bodies that drive the engine (`start_step`, `handle_agent_event`, `route_workflow`). Workflows are typed data, registered at startup; the engine is mechanism, not policy. Phase 0b ships an empty skeleton — Phase 1 wires the data structures, registries, and async event-driven model.

## Public interface

Empty in Phase 0b. Phase 1 adds: `Workflow`, `Step`, `WorkflowCommand` interface, `Outcome` union, `WorkflowEngine`, `register_workflow`, `register_command`, `start`.

## Module architecture

Phase 1+. See [plan/milestones/M05-workspace-agent/architecture.md § Workflow + WorkflowCommand model](../../../plan/milestones/M05-workspace-agent/architecture.md#workflow--workflowcommand-model) for the design.

## Data owned

Phase 1+. Will own `workflow_executions` and `pending_human_decisions`.

## How it's tested

Phase 1 adds coverage for Local-only workflow, Workspace step async cycle, failure + retry, HITL pause + resume, append_steps, backend-restart with `awaiting_agent` workflows, cancellation, idempotent duplicate event handling, and an async-model load test.
