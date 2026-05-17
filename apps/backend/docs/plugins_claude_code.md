# plugins/claude_code

> Wraps the Claude Code CLI as a `domain/coding_agent.CodingAgentPlugin`. Owns prompt assembly, output parsing, and Anthropic credentials.

## Purpose

Adapter for [Claude Code](https://docs.claude.com/en/docs/claude-code), the only coding-agent CLI in M01. Implements `review`, `reply`, `validate_config`, `health_check`. Owns prompt assembly (system framing, persona, diff/lessons/comments, JSON-schema appendix) and the plugin-internal output schema (`_FindingDto`, `_FindingList`, `_ReplyResponse`). Converts agent text → `vcs.Finding` before results leave the plugin. Knows nothing about yaaos tickets, review jobs, audit log, or the workspace's working directory.

## Public interface

- Singleton `ClaudeCodePlugin` registered into `domain/coding_agent` at `bootstrap()`; also registers `anthropic_key_set` onboarding contributor.
- Side-effect import of `web.py` wires HTTP routes (prefix `/api/claude_code`):
  - `POST /api_key` — set/rotate the Anthropic key (`{api_key: str}`). Empty rejected with 400. Fernet-encrypts, upserts on `claude_code_settings`, invalidates the auth-probe cache.
  - `GET /health` — wraps `health_check()`.
- Plugin credentials live under the plugin's own URL space, not a generic `/api/settings/*` (see `docs/architecture.md`).
- Domain code never imports this module; uses `domain/coding_agent`'s registry.

## Module architecture

Singleton constructed at import time. Holds no decrypted credentials — settings loaded per-invocation, so key rotation takes effect immediately.

### `review` / `reply`

Both share `_prepare_invocation` + `_run_and_parse_envelope`, differing only in prompt content and JSON schema appended.

**Step 1 — load settings + build argv (`_prepare_invocation`):**

`_load_settings_for_invocation` selects the single `claude_code_settings` row and decrypts the Anthropic key. Returns `(api_key, cli_path, default_timeout_seconds)`. No key or no CLI path (`claude_code_settings.cli_path` or `shutil.which("claude")`): early `AGENT_ERROR`.

Argv: `claude --print --output-format=json --permission-mode=bypassPermissions --allowed-tools=Read,Glob,Grep,LS,NotebookRead,TodoWrite,WebFetch,WebSearch` plus optional `--model` / `--max-turns` from `agent_config`. Read-only tools only — no `Bash`, `Write`, `Edit`. Web tools enabled for CVE / library lookups. `agent_config["timeout_seconds"]` overrides the 600s default.

Env: copy of `os.environ` with `ANTHROPIC_API_KEY` injected. Key never on argv.

**Step 2 — assemble prompt + schema appendix:**

`_assemble_review_prompt(ctx)` builds: `# Agent: <name>` header, persona, optional repo-language block, PR title/body, fenced diff, optional lessons (title + id + body), optional prior sibling-agent comments (truncated to 20 items × 200 chars).

`_assemble_reply_prompt(ctx)` is simpler: header + persona + reply being responded to + diff context.

`_schema_appendix(model)` appends a STRICT instruction with `model.model_json_schema()`. This is the only mechanism constraining output shape — Claude Code's `--output-format=json` controls the wrapper envelope, not content.

**Step 3 — run via workspace:**

Workspace owns subprocess lifecycle (`cwd`, process group, SIGTERM → 2s grace → SIGKILL). Prompt piped via stdin (avoids `ARG_MAX`). Plugin sees only `CodingAgentCliResult`.

`WorkspaceExecError` → `AGENT_ERROR`. `timed_out=True` → `TIMEOUT`. Non-zero exit → `AGENT_ERROR` with first stderr line.

**Step 4 — parse wrapper envelope:**

`--output-format=json` emits `{result, usage: {input_tokens, output_tokens}, total_cost_usd}`. Plugin extracts `result` and populates `InvocationTelemetry` with latency, tokens, cost. `total_cost_usd` left None when absent. Envelope-parse failure → `AGENT_ERROR` with raw output in `telemetry.raw_output`.

**Step 5 — strict-parse agent response:**

Strict JSON parse → validate against `_FindingList`. No markdown-fence fallback. Failure → `PARSE_FAILURE` with raw text in `telemetry.raw_output`; reviewer can audit and re-prompt.

**Step 6 — convert to vendor-neutral types:**

`_dto_to_finding(dto)` maps `_FindingDto` → `vcs.Finding`. `_compute_state(findings)`: empty → `APPROVED`, any `must-fix` → `CHANGES_REQUESTED`, else `COMMENT`.

Reply path identical shape, uses `_ReplyResponse` (single `body: str`).

### `validate_config`

Schema check only. Allowed keys: `timeout_seconds` (positive int), `max_turns` (positive int), `model` (non-empty string). Unknown keys error. No model-id enumeration — Anthropic ships new ones often.

### `health_check`

Cascade:
1. No API key → `"anthropic api key not set"`.
2. No `claude` binary → `"claude binary not found"`.
3. Probe Anthropic via `_probe_anthropic_auth(api_key)`.

### Anthropic auth probe

Real `GET https://api.anthropic.com/v1/models` with configured key. `200` → ok. `401`/`403` → "anthropic api key is invalid". Other → error message naming the failure.

Cached in module-level `_AUTH_CACHE` keyed on `sha256(api_key)`, 5-minute TTL. Fingerprint key survives same-value reads and resets on key change. `_set_anthropic_key` explicitly invalidates on rotation so a stale "healthy" can't be served.

**Stub-mode bypass.** When `YAAOS_CODING_AGENT_STUB` is set, probe short-circuits to ok for any non-empty key. The stub plugin (`testing_stub_coding_agent.md`) never calls Anthropic anyway.

### Onboarding contributor

`_onboarding_anthropic_key_set(org_id)` returns True iff encrypted key row exists AND the key authenticates against Anthropic via the cached probe. Saved-but-invalid keys (typo, revoked) do not satisfy the prereq — would otherwise leave onboarding green when reviews would fail.

### Concurrency

Singleton; concurrent `review` / `reply` calls expected. Each spawns its own subprocess and reads its own settings row. No per-call state; no locks.

### Test-mode wrapping

This file never branches on test env vars. When `YAAOS_CODING_AGENT_STUB` is set, `app/main.py` calls `testing.stub_coding_agent.wrap_all_registered_plugins()` after `bootstrap()` runs. See `testing_stub_coding_agent.md`.

## Data owned

- `claude_code_settings` — one row per org. Columns: `encrypted_anthropic_api_key`, `default_model` (optional), `cli_path` (optional), `default_timeout_seconds` (default 600).

## How it's tested

Unit tests in `app/plugins/claude_code/test/`:

- `test_prompt_and_state.py` — prompt assembly (persona, diff, lesson titles + ids, prior-comment truncation) and verdict computation. Schema appendix and DTO conversion validated through the same path.

CLI subprocess + envelope parsing + Anthropic auth probe are exercised end-to-end by e2e tests with `YAAOS_CODING_AGENT_STUB=1` swapping in `StubCodingAgentPlugin`.
