"""core/sse_pubsub — thin wrapper over Redis pub/sub for ActivityEvent fanout.

Phase 0b ships the scaffold. Phase 8b's WebSocket plumbing publishes to
`activity:{workflow_execution_id}`; the SSE handler in `web.py` subscribes
per workflow execution. M05 Phase 0b: empty skeleton.
"""

__all__: list[str] = []
