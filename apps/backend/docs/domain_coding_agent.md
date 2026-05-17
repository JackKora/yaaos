# domain/coding_agent

> Vendor-neutral abstraction over coding-agent CLIs (Claude Code, Codex, Aider) — Protocol, registry, dispatch.

## Purpose

The contract between yaaos and external agent CLIs. Owns the `CodingAgentPlugin` Protocol (with targeted methods `review` and `reply` — not a generic `invoke`), structured input contexts (`ReviewContext`, `ReplyContext`), vendor-neutral output types (`ReviewResult`, `ReplyResult`), telemetry/status enums, the plugin registry, and the typed exception hierarchy. Owns **zero prompt assembly** and **zero output-format choice** — plugin concerns. yaaos makes no LLM API calls; plugins shell out to CLIs via `core.workspace.Workspace`.

Lives in `domain/` (not `core/`) because return types reference `vcs.Finding` and `memory.Lesson`. See [`modularity.md`](modularity.md).

## Public interface

Exported from `app/domain/coding_agent/__init__.py`:

- Types — `AgentSpec`, `ReviewContext`, `ReplyContext`, `ReviewResult`, `ReplyResult`, `InvocationStatus`, `InvocationTelemetry`, `ValidationResult`, `HealthStatus`.
- Protocol — `CodingAgentPlugin`.
- Registry/dispatch — `register_coding_agent_plugin`, `get_plugin`, `registered_plugin_ids`, `review`, `reply`, `validate_config`, `health_check_all`, `_reset_plugins_for_tests`, `_PLUGINS`.
- Exceptions — `CodingAgentError`, `PluginNotFoundError`, `CodingAgentCacheMiss`.

No HTTP routes.

## Module architecture

### Types (`types.py`)

- `AgentSpec` — persisted definition: `name`, `prompt_text` (persona/focus), `coding_agent_plugin_id`, plugin-specific `agent_config`. Persona is content the plugin weaves into its own structural framing.
- `ReviewContext` — `persona`, `agent_name`, `pr`, `diff`, `lessons`, optional `language_hint`, `prior_yaaos_comment_bodies`, `agent_config`.
- `ReplyContext` — `persona`, `agent_name`, `pr`, `diff`, `reply_body`, `parent_comment_external_id`, `agent_config`.
- `InvocationStatus` — `SUCCESS` / `PARSE_FAILURE` / `AGENT_ERROR` / `TIMEOUT`.
- `InvocationTelemetry` — `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `raw_output`, `raw_stderr`.
- `ReviewResult` — `status`, `findings` (already `vcs.Finding`s — consumers wrap them in a `vcs.Review` and call `vcs_plugin.post_review`), optional `state` / `summary_body`, `lesson_ids_consulted`, `telemetry`, optional `error_message`.
- `ReplyResult` — `status`, optional `body`, `telemetry`, optional `error_message`.
- `ValidationResult` — `valid`, `errors`.

### `CodingAgentPlugin` Protocol

Async methods `review`, `reply`, `validate_config`, `health_check` plus `meta: PluginMeta`. Signatures in `app/domain/coding_agent/types.py`.

`review` and `reply` MUST NOT raise on agent-level failures (timeout, non-zero exit, malformed JSON) — those become `status` + `error_message` so consumers branch on the same surface. Only infrastructure failures (e.g., `WorkspaceExecError`) are raised.

### Registry + dispatch (`service.py`)

Process-global `_PLUGINS` keyed by `plugin.meta.id`. `register_coding_agent_plugin` rejects duplicates. `review` / `reply` are thin wrappers that resolve the plugin, forward the call, and emit `agent.reviewed` / `agent.replied` log lines carrying telemetry. No retry, no fallback — caller policy. `health_check_all` converts any raised exception to an unhealthy `HealthStatus`. `_reset_plugins_for_tests()` clears the registry.

### Failure model

The status-not-exception contract means a malformed JSON response or a timeout becomes `ReviewResult(status=PARSE_FAILURE, …)`, not a raised exception. Consumers (`reviewer`) branch on `result.status` to decide whether to mark the job failed, retry, or surface partial output.

## Data owned

None. Registry is in-memory; `AgentSpec` is persisted by `reviewer` in `reviewer_agents`.

## How it's tested

`app/domain/coding_agent/test/test_registry.py` — register/get/duplicate-rejection, dispatcher logging, `validate_config` forwarding, `health_check_all` exception-to-unhealthy. Uses a fake plugin. Plugin-specific behaviour covered by each plugin's tests under `app/plugins/<plugin>/test/`.
