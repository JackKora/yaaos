# Glossary

Shared vocabulary across backend and frontend. These terms appear in code, URLs, and UI; this list keeps usage consistent.

| Term | Meaning |
|---|---|
| **Org** | Tenant boundary. One org today; every domain function takes `org_id`. |
| **Ticket** | yaaos's unit of work. References a PR; flows `open` → `in_review` → `complete` / `abandoned`. |
| **PR** | The VCS-side artefact. Mirrored from GitHub into `pull_requests`. Owned by `domain/pull_requests`. |
| **Review job** | One agent's attempt to review one PR. Three per ticket (architecture / security / style). States: `queued` → `running` → `posted` / `failed` / `skipped` / `cancelled`. Owned by `domain/reviewer`. |
| **Agent** | A reviewer persona — a row in `reviewer_agents` with `name`, `prompt_text`, `coding_agent_plugin_id`. Three built-ins ship; prompts editable in UI. |
| **Coding agent** | The external CLI yaaos shells out to (Claude Code). Protocol: `domain/coding_agent.CodingAgentPlugin` with `review` / `reply`. yaaos never calls an LLM directly. |
| **Workspace** | Provisioned environment where the CLI runs (tempdir + git clone today). Lifecycle owned by `core/workspace`; provisioning via `WorkspaceProvider` plugins. |
| **Finding** | One reviewer comment: `file`, `line_start`/`line_end`, `severity` (`must-fix` / `nit` / `suggestion` / `info`), `title`, `body`, optional `rationale`, optional `snippet`. Vendor-neutral; defined in `domain/vcs`. |
| **Lesson** | Repo-scoped institutional memory: `{title, body, source_pr_url}`, 1000-char body cap. Surfaces in agent prompts; UI shows applied-lesson chips. Owned by `domain/memory`. |
| **Plugin** | Vendor-specific implementation of a Protocol in `domain/` or `core/`. Three Protocols: `VCSPlugin` (github), `CodingAgentPlugin` (claude_code), `WorkspaceProvider` (in_process_workspace). Vendor SDKs only allowed in `apps/backend/app/plugins/`. |
| **Verdict** | Terminal state of a posted review: `APPROVED` / `CHANGES_REQUESTED` / `COMMENT`. Decided by the CLI; returned in `ReviewResult.state`. |
| **Skip reason** | Why a job didn't run: `fork`, `bot_author`, `trivial_diff`, `too_large`, `secrets_detected`, `ui_cancel`, `superseded`. Recorded on the row and rendered in UI. |
| **Audit entry** | One row in `audit_log`. Append-only. Kind is `<entity>.<verb_past>`. Payload is a Pydantic model owned by the writing module. |
| **Actor** | Who initiated an action — `{kind: "github_user" | "agent" | "system", login?, agent_id?}`. Required on every audit entry. Defined in `core/primitives`. |
| **Persona** | The agent's `prompt_text` — system framing handed to the CLI verbatim. Edited via the Prompts page. |
| **Onboarding** | Dashboard's pre-ready state. Two checks: GitHub App installed + Anthropic API key set (validated by live probe). Computed by `domain/settings.get_onboarding_status()`. |
