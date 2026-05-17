# domain/reviewer

> Review workflow orchestrator — reviewer agents, per-PR queue, review-job state machine, heartbeat, secrets pre-flight, frozen-snapshot audit, step-progress SSE, startup recovery.

## Purpose

The busiest backend module. Owns the `ReviewJob` aggregate (one row per `(PR, agent, scheduling event)`), the three built-in reviewer agents (architecture, security, style), and the lifecycle from "needs review" through workspace provisioning, coding-agent invocation, finding parsing, and posting. Does not call LLMs directly — Claude Code does, behind the `domain/coding_agent` Protocol. Owns scheduling, debouncing, cancellation, audit trail, and cooperative-cancellation runtime on `core/primitives.spawn`.

## Public interface

Exported from `app/domain/reviewer/__init__.py`:

- Types — `ReviewJob`, `ReviewJobInput`, `ReviewerAgent`, `ReviewJobStatusChanged`, `ReviewJobRow`, `PostedCommentRow`, `ReviewerAgentRow`, `AgentNotFoundError`.
- Scheduling — `schedule_review`, `schedule_reply`, `cancel_pending`.
- Reads — `get_review_job`, `list_review_jobs_for_pr`, `list_in_flight`, `metrics_summary`.
- Agents — `list_agents`, `get_agent_by_id`, `get_agent_by_name`, `update_agent_prompt`, `reset_agent_prompt`, `ensure_builtin_agents`.
- Lifecycle — `startup_recovery`.

HTTP routes (`/api/reviewer`):

- `GET /agents` — list the three reviewer agents.
- `PUT /agents/{name}/prompt` — body `{ prompt_text }`; 400 on empty.
- `POST /agents/{name}/reset_prompt` — restore built-in default.
- `POST /rereview` — body `{ ticket_id }`; UI button.
- `POST /cancel?ticket_id=...` — cancel queued/running jobs.
- `GET /jobs/by-ticket/{ticket_id}` — every review_job for the ticket's PR.
- `GET /metrics` — aggregate counters.

Route spec registers two `on_startup` hooks: `startup_recovery` and `_seed_builtin_agents`.

## Module architecture

### Files

- `models.py` — `ReviewerAgentRow`, `ReviewJobRow`, `PostedCommentRow`.
- `agent_crud.py` — `ReviewerAgent` view model + CRUD.
- `seeds.py` — `DEFAULT_PROMPTS` and `builtin_prompt(name)`.
- `queue.py` — events, audit payloads, `schedule_*`/`cancel_pending`, reads, `_run_review_job`, `_run_reply_job`, transitions, secrets detection, language detect, `startup_recovery`.
- `web.py` — routes.

### Per-PR queue discipline

"At most one in-flight `ReviewJob` per `(pr_id, agent_id)`" — enforced by service logic, not a unique index. `schedule_review` flips every `queued`/`running` row for the pair to `cancelled` with `skip_reason='superseded'`, writes `review_job.cancelled` audit, inserts the new `queued` row, spawns the handler.

Cancellation is DB-driven and cooperative. No task IDs. The coro polls its row at three safe points — after debounce, after entity resolution, after workspace provisioning — and returns early when status flips off `queued`/`running`.

### `schedule_review` — main entry point

Called by `intake` for `pr_ready`, `pr_synchronized`, `rereview_command`, and the UI's re-review button. Accepts `agent_names="all"` (expands to the three names) or an explicit list. For each: cancels in-flight, inserts queued, writes `review_job.scheduled` audit, publishes `ReviewJobStatusChanged(status="queued")`, spawns `_run_review_job`. Debounce from `core.config.Settings.yaaos_review_debounce_seconds` (30s prod, 0s tests).

### `_run_review_job` — state machine handler

Fire-and-forget coro:

1. **Debounce sleep** if positive.
2. **Bail check** — re-read; if no longer `queued`, return. Freshly-scheduled reviews win the race.
3. **Flip to running** — status, `started_at`, `last_heartbeat_at`, `current_step='resolving_entities'`.
4. **Resolve entities** — ticket, PR, agent.
5. **Step progress** — `_set_step("fetching_diff", ...)` updates `current_step`, bumps heartbeat, publishes `ReviewJobStepProgress`.
6. **Fetch context** — lessons via `memory.list_for_repo`, diff via `vcs_plugin.fetch_diff`, prior yaaos comments via `vcs_plugin.list_yaaos_comments`.
7. **Skip checks** — `is_fork`, `author_type == "bot"`, every diff file matches `intake.is_skippable_path` (trivial), or `additions + deletions > 5000` (too large). On match → `skipped(skip_reason=...)`.
8. **Secrets pre-flight** — `_detect_secrets(diff)`. On match, post a one-shot refusal review, transition `skipped(skip_reason="secrets_detected")`.
9. **Language detect** — walks `diff.files`, returns most common extension or `None`.
10. **Build `ReviewContext`** — plugin owns prompt assembly and response-schema choice.
11. **Hash + snapshot** — `prompt_hash = sha256(ctx.model_dump_json())`, denormalize hash and `lessons_applied`, write `review_job.prompt_sent` audit with frozen `_AgentSnapshot`, hash, lesson IDs, checkout SHA, language hint.
12. **Provision workspace** — `with_workspace("in_process", ...)`.
13. **Final bail check** inside the workspace context.
14. **Invoke** — `coding_agent.review(plugin_id, workspace, context)`.
15. **Post result** — on `SUCCESS`: build `vcs.Review`, call `post_review`, write one `PostedCommentRow` per finding-that-became-a-comment, update row (`status='posted'`, telemetry, JSON findings); write `review_job.posted` audit; publish status change. Non-success → `_transition_failed`.

Uncaught exceptions log `review_job.handler_crashed` and convert to `failed` (no re-raise — fire-and-forget).

### Step-progress SSE

`_set_step` writes `current_step` + `last_heartbeat_at` and publishes `ReviewJobStepProgress`. Frontend subscribes and invalidates the per-ticket query. Phases: `resolving_entities` → `fetching_diff` → `provisioning_workspace` → `invoking_agent` → `posting_review` → (`posted`|`failed`). Step changes generate no audit entries. Audit captures *scheduled*, *prompt_sent*, *posted*, *failed*, *skipped*, *cancelled*, *reply_posted*.

### Heartbeat

`last_heartbeat_at` is bumped on every `_set_step` — no separate heartbeat coroutine. The admin Activity page and stuck-job detection both read it.

### Secrets pre-flight

Five regex rules catch high-confidence shapes: AWS access key, GitHub token, Anthropic key, OpenAI key, PEM private-key block. `_detect_secrets` scans only `+`-prefixed lines in `diff.raw` (excluding `+++` headers), returns the first matching rule id. On match: one refusal review (`state="COMMENT"`, empty findings) and `skipped(skip_reason="secrets_detected")`. Audit carries the rule id, never the matched bytes. Three agents run independently — up to three warnings may post; deduping out of scope.

### Reply workflow

`schedule_reply` is lighter. Creates a `kind='reply'` row with `parent_comment_external_id` and `reply_body`, spawns `_run_reply_job` with zero debounce, supersedes any in-flight reply for the same triple. The handler builds a `ReplyContext`, provisions a workspace, calls `coding_agent.reply`, posts via `vcs_plugin.post_comment_reply` (not a top-level review). No `posted_comments` row. Audit kind `review_job.reply_posted`.

### Frozen-snapshot audit payload

`review_job.prompt_sent` carries a full `_AgentSnapshot` (id, name, prompt_text, plugin id, agent_config), prompt hash, lesson IDs, checkout SHA, language hint. Immutable — later prompt edits don't rewrite history.

### Denormalized fields on `review_jobs`

Beyond lifecycle: `prompt_hash`, `lessons_applied` (UUID[]), `tokens_in`, `tokens_out`, `cost_usd`, `duration_s`, `error_message`, `review_external_id`, JSON-dumped `findings`. Convenience views — audit log remains historical truth.

### Agent CRUD + seeding

`ensure_builtin_agents` (idempotent, `on_startup`) inserts missing rows from `DEFAULT_PROMPTS` with `coding_agent_plugin_id="claude_code"`, empty `agent_config`, `is_built_in=True`. `update_agent_prompt` and `reset_agent_prompt` write `reviewer_agent.prompt_updated` audit with `{prior_hash, new_hash, restored_to_default?}` — text not stored in audit.

### Startup recovery

`startup_recovery` (`on_startup`) does in one transaction: select `running` ids (crashed processes), flip them to `failed` with `skip_reason='crashed'`, select all `queued`. After commit, writes `review_job.failed` per crashed id and respawns `_run_review_job` for each queued (zero debounce). `queued` rows auto-resume; `failed` requires operator re-review.

### In-flight tracking

`list_in_flight` returns `status in ('queued','running')`. No separate task registry, no broker. The domain row is the truth.

### Metrics

`metrics_summary` walks all rows once: `{review_jobs_by_status, total_reviews_posted, total_cost_usd, failure_count, failure_rate}`. Backs `GET /api/reviewer/metrics`.

## Data owned

- `reviewer_agents` — one row per agent. Unique on `(org_id, name)`.
- `review_jobs` — one row per `(PR, agent, scheduling event)`. Indexed on `(pr_id, status, created_at)` and `(status, last_heartbeat_at)`.
- `posted_comments` — one row per VCS comment yaaos has posted; PK `external_comment_id`. Read by `intake` to resolve "which agent owns this comment".

Canonical schema in [core_database.md](core_database.md).

## How it's tested

`app/domain/reviewer/test/test_detect_secrets.py` exhaustively covers the pre-flight detector. Scheduling, supersession, the handler state machine, replies, and startup recovery are covered by integration suites in `app/test/` and e2e tests in `apps/e2e/`.
