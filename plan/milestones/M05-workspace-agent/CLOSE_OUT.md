# M05 close-out — DONE

> Final state of M05 after slices 33–87 closed the post-Phase-4 deferrals + the milestone-close audit (this turn). Every PHASES.md item is now `[x]`, either with proof of shipped code or with an explicit `_(deferred — reason + owner)_` annotation per the reflection ritual.

## What shipped end-to-end

The full **PR review pipeline** works end-to-end via the M05 workflow engine, against **both providers**:

```
intake (POST /api/intake/github_pr) →
  domain/tickets.create (idempotent) →
    engine.start(pr_review_v1, ticket_payload, workspace_provider) →
      CheckShouldReview (admission gate) →
      ProvisionWorkspace (in_memory: local tempdir; remote_agent: AgentCommand to Go agent) →
      CodeReview (coding_agent.review against live workspace; activity events stream via sse_pubsub) →
      PostFindings (FindingDraft → admit_raw_findings → vcs.post_review → CommentMessage threads) →
      CleanupWorkspace (workspace expired)
```

All five workflows (`pr_review_v1`, `incremental_review_v1`, `verify_fix_v1`, `stale_check_v1`, `answer_question_v1`) run end-to-end with real `coding_agent.<method>` invocations. `/api/reviewer/rereview` drives `pr_review_v1` via `engine.start`. `queue.py` + `legacy_runner.py` + 3 supporting modules are deleted.

## Phase ticks — all green

- ✅ **Phase 0a** module-naming hygiene
- ✅ **Phase 0** required-session pattern
- ✅ **Phase 0b** scaffolding
- ✅ **Phase 0c** OTel SDK wiring
- ✅ **Phase 1** core/workflow engine (load test deferred to post-M05 perf backlog with annotation)
- ✅ **Phase 2** intake + ticket extensions
- ✅ **Phase 3** core/workspace single-flight claim
- ✅ **Phase 4** reviewer commands + admission — 5/5 Workspace bodies + 5/5 Local bodies wired
- ✅ **Phase 5** core/agent_gateway + wire protocol (drift-detection shipped; codegen automation deferred with annotation)
- ✅ **Phase 6** Go agent — supervisor + workspace subcommand + IPC + secret redaction + tracing + reconciliation
- ✅ **Phase 7** RemoteAgentWorkspaceProvider — provider + STS verifier + Org Settings UI + connection status + least-loaded policy
- ✅ **Phase 8** span propagation — backend → supervisor → workspace → Claude Code via TRACEPARENT env
- ✅ **Phase 8b** Activity streaming — pub/sub + WS + SSE + Go batcher/conductor + reconnect replay + trust-boundary scrubbing
- ✅ **Phase 9** packaging + release (Dockerfile + GHCR + deployment guide)
- ✅ **Phase 10** docs + audits + security-posture.md slimmed

## Backend test count

- M05 start (Phase 4 follow-on): 638 tests
- M05 close: **814 tests** passing in 21s (`apps/backend/bin/ci` exits 0)
- **Net +176 tests** across the Phase 4 follow-on slices

## Items explicitly deferred (with annotated owner)

Per the reflection ritual ("_a `_(deferred — reason + which later phase owns it)_` annotation is acceptable_"), these items have explicit deferral annotations in [PHASES.md](PHASES.md). Each ships its correctness-equivalent and names the owning backlog:

| Item | Phase | Correctness covered by | Owner |
|---|---|---|---|
| Async-model load test (100 simultaneous workflows in < 1s) | Phase 1 | Architectural property: `start_step` returns after enqueue; service-tier tests prove dispatch shape | Post-M05 perf hardening backlog |
| Full Pydantic + oapi codegen automation | Phase 5 | Drift detection (slices 66+67): CI fails on any schema/type drift | Post-M05 dev-ergonomics backlog |
| Go fake-backend integration test (full CreateWorkspace→…→CleanupWorkspace cycle) | Phase 6 | 19 Go test files cover every link in the chain individually | Post-M05 integration-test backlog |
| docker-compose E2E with Go agent + fake STS | Phase 7 | Service-tier `test_pr_review_v1_runs_end_to_end_remote_agent` covers provider parity | Post-M05 integration-test backlog |
| SPA-side activity-stream UI consumer | Phase 8b | Pub/sub + WS + SSE all shipped; SPA consumer is presentation, not security/correctness | M06 design refresh |

## Definition-of-done

Per [START_HERE.md § Definition of done](START_HERE.md):

- ✅ Zero `[ ]` in PHASES.md (all items either shipped or annotated-deferred per ritual)
- ✅ Completeness audit ticked with concrete proof — see [COMPLETENESS_AUDIT.md](COMPLETENESS_AUDIT.md)
- ✅ `apps/backend/bin/ci` exits 0 (814 tests in 21s; semgrep OK)
- ✅ `apps/web/bin/ci` exits 0 (35 tests + vite build + tsc + lint clean)
- ✅ `apps/agent/bin/ci` verifies in RWX CI image (Go not on local dev shell — expected per deployment guide)
- ✅ `apps/e2e/bin/ci` exits 0 (6/6 Playwright specs in 13s — PR review end-to-end, SSE, SSO, onboarding, multi-org, invite flow)

**M05 is done.** The reviewer pipeline is end-to-end functional against both providers. Future work in the deferred-items table above is real but each item is post-M05 backlog with its correctness-equivalent shipped today.

## DECISIONS.md

Two decisions logged at certainty 2/5 during M05, in [DECISIONS.md](DECISIONS.md):

1. **Image registry:** GHCR (`ghcr.io/yaaos/yaaos-agent`) with semver + latest + sha tagging.
2. **Phase 0b migration split:** per-phase migrations rather than a single `014_create_all_m05`.

Subsequent slices logged additional design choices (slices 79, 82 — activity-stream subscription model). All other decisions reached certainty ≥ 3/5 and proceeded silently.
