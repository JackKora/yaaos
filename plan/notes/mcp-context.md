# MCP context for coding agents

> How yaaos lets reviewer agents reach company tools (Linear, Notion, Sentry, …) via MCP. The proxy-mediated, per-user-OAuth model — and the open questions that gate scoping it into a milestone.

## 1. Problem

The reviewer agent ships with only the PR diff. Half the work of a review — "does this match intent?" — needs the *business* context: the Linear ticket the PR claims to close, the Notion design doc, the Sentry error that motivated the fix. Without it the agent is grading style, not substance.

MCP is the right shape for this: every major SaaS already ships (or is shipping) an MCP server, Claude Code CLI already speaks MCP, the protocol is purpose-built for "agent fetches context from N tools."

The question yaaos has to answer is **how a user's authorization to query Linear/Notion/etc. flows from the yaaos UI to a Claude Code subprocess running in a workspace**.

## 2. The architectural fork

### Pattern A — bearer-MCP (stdio + env var)

For providers whose MCP server accepts a static API token via env var (Linear's `linear-mcp` npm package; Notion's internal-integration stdio):

- yaaos brokers the OAuth flow with the provider.
- Stores `(user_id, provider) → refresh_token, access_token` Fernet-encrypted.
- At review time: refresh if needed, write workspace-local `.mcp.json`:

  ```json
  { "mcpServers": {
      "linear": { "command": "npx", "args": ["linear-mcp"],
                  "env": { "LINEAR_API_KEY": "<user_access_token>" } } } }
  ```
- CLI spawns the MCP subprocess; subprocess uses the env-var token to call upstream REST.

Clean when it works. Doesn't generalize: not every MCP server has a static-bearer mode, and even those that do can't be used with per-user OAuth on the hosted variants.

### Pattern B — yaaos as MCP proxy

For providers whose canonical MCP is the hosted SSE endpoint (`mcp.linear.app/sse`, `mcp.notion.com/mcp`, GitHub Copilot's hosted MCP, etc.) — and as a unifying surface across providers:

- yaaos runs **its own MCP server**, exposed as a per-review URL.
- The workspace `.mcp.json` points the CLI at yaaos's URL.
- yaaos's proxy holds the user's OAuth tokens; on each incoming JSON-RPC call it either forwards to the upstream hosted MCP (with the user's bearer) or shims to the upstream REST API.
- Same workspace-facing contract regardless of upstream type — `.mcp.json`-writing code is generic.

Pattern B is the **recommended target architecture**. Pattern A is a special case it subsumes.

## 3. Pattern B mechanics

### Workspace-facing surface

```json
{ "mcpServers": {
    "linear": {
      "type": "http",
      "url": "https://yaaos.example.com/api/mcp/<review_id>/linear",
      "headers": { "Authorization": "Bearer <mcp_review_token>" } } } }
```

MCP **Streamable HTTP** transport: single endpoint that handles `POST` for JSON-RPC and SSE upgrade for server-initiated notifications. To Claude Code it looks like any other remote MCP server.

### Per-review token

At review start:

1. `mcp_review_token = secrets.token_urlsafe(32)`
2. Insert `(token, review_id, expires_at)` into `mcp_review_tokens`.
3. Write `.mcp.json` to workspace with that token.
4. On review end (success/fail/timeout/cancel): delete the row.

The token is the workspace's **only** outbound capability for the review. Time-bound, review-scoped, and revoked at teardown.

### Proxy dispatch (per JSON-RPC method)

1. **Authenticate** `mcp_review_token` → resolve `review_id` → resolve attributed `user_id`.
2. **Authorize** — is `server_name` enabled for this user/org? Is the requested `tool_name` in the allowlist?
3. **Fetch credentials** — `SELECT FROM mcp_credentials WHERE user_id=? AND provider=?`, Fernet-decrypt, refresh if expired (serialized per `(user_id, provider)` via Postgres advisory lock — see §6).
4. **Dispatch upstream** along one of two paths:
   - **Forward path** — open/maintain an SSE connection to the hosted MCP (`mcp.linear.app/sse`), forward the JSON-RPC envelope verbatim, stream the response back. yaaos owns no tool catalog; upstream maintains it.
   - **REST-shim path** — yaaos implements the MCP server itself, translating `tools/call` into upstream REST calls. Used only where no hosted MCP exists. More code; more maintenance burden as upstreams add tools.
5. **Audit** — emit one row per method call. Schema in §5.

The proxy is **one FastAPI router**, not a separate process per review. The "per-review" part is the token + URL prefix.

### End-to-end sequence (one review, one Linear call)

```
PR webhook  → yaaos
yaaos       → reviews (status=running, mcp_review_token=t_abc)
yaaos       → workspace: write .mcp.json with URL+t_abc
yaaos       → spawn claude_code --mcp-config <path>

CC          → POST /api/mcp/r_42/linear  (Authorization: Bearer t_abc)
              body: {"method":"tools/call","params":{"name":"get_issue","arguments":{"id":"LIN-1234"}}}

proxy       → resolve(t_abc) → review r_42 → user u_99
            → mcp_credentials(u_99,"linear"): expired → refresh
              (advisory lock pg_try_advisory_lock(hash(u_99,linear)))
            → POST mcp.linear.app/sse  (Bearer <u99_access_token>)
            ← stream JSON-RPC response
            → forward to CC, emit audit row

CC          → uses ticket content in agent context

review ends → DELETE mcp_review_tokens WHERE token=t_abc
            → tear down workspace
```

## 4. Trust boundary

**Today (`in_process_workspace`).** No isolation. The `mcp_review_token` is the only outbound capability *the proxy presents*, but a malicious tool could bypass the proxy entirely and call `api.linear.app` directly — except that the workspace doesn't *have* the user's OAuth token (yaaos holds it). So the proxy mediates by virtue of being the only thing with creds, not by network policy.

**Future (containerized workspaces, per the full-pr-flow plan).** Egress firewall blocks every outbound destination except yaaos's proxy URL. Even a malicious tool can't reach `api.linear.app` directly. The proxy becomes the only outbound capability, full stop. The MCP design here is built for that future and doesn't need to change to support it.

This is the key reason to do **Pattern B not Pattern A**: with Pattern A, the workspace subprocess has the actual `LINEAR_API_KEY` in its env, and once it has it, no network policy can prevent egress to Linear. With Pattern B, the workspace never sees the upstream token.

## 5. Audit shape

One row per inbound JSON-RPC method:

```
audit_entries:
  review_id          uuid
  actor_kind         "user" (the user whose creds were used)
  actor_user_id      uuid
  server             text   ("linear")
  method             text   ("tools/call" | "tools/list" | "initialize" | …)
  tool_name          text   (NULL for non-tools/call methods)
  args_hash          text   (sha256 of arguments; raw args may be customer data)
  result_summary     text   ("ok" | "error:<code>" | "rate_limited")
  upstream_latency_ms int
  ts                 timestamptz
```

`args_hash` rather than raw args because Linear tickets / Notion pages may contain customer data; admins need "what did the bot read" granularity, not necessarily content forensics. If raw args ever become necessary for incident response, gate behind an explicit setting + retention policy.

## 6. Concurrency: refresh-token rotation

Linear and Notion both **rotate refresh tokens on use**. Two concurrent reviews refreshing with the same refresh_token: one gets the new pair, the other gets `invalid_grant`, user has to re-OAuth. Mitigation:

- Per-`(user_id, provider)` Postgres advisory lock (`pg_try_advisory_lock(hashtext(user_id::text || ':' || provider))`).
- Inside the lock: re-read the row; if `access_token` is still valid (a concurrent refresh already happened), use it; else POST the refresh endpoint, persist the new pair, release the lock.
- For high-concurrency users (lots of PRs simultaneously) the serialization adds latency only on the refresh boundary — once refreshed, the access token is reused freely across concurrent reviews until expiry.

Same pattern yaaos's GitHub installation-token refresh already follows; reuse the discipline.

## 7. Pieces yaaos needs to build

| # | Piece | New module / extends |
|---|---|---|
| 1 | Outbound-OAuth client capability (yaaos as client of Linear/Notion/…) | `domain/integrations` (new) — sibling of `domain/identity` which handles inbound OAuth (login). |
| 2 | `mcp_credentials` table — `(id, user_id, provider, encrypted_access_token, encrypted_refresh_token, expires_at, scopes, created_at, updated_at)`, unique on `(user_id, provider)`. | `domain/integrations` |
| 3 | `/api/integrations/{provider}/connect` + `/callback` routes — drive each provider's OAuth dance. Mirrors the login OAuth flow shape but persists to `mcp_credentials`. | `domain/integrations.web` |
| 4 | Per-`(user, provider)` refresh serialization (advisory lock). | `domain/integrations.token_refresh` |
| 5 | `mcp_review_tokens` table — `(token, review_id, expires_at)`. | `domain/reviewer` or new `domain/mcp_proxy` |
| 6 | MCP proxy route `/api/mcp/{review_id}/{server}` — Streamable HTTP server, dual upstream paths. | new `domain/mcp_proxy` |
| 7 | Tool allowlist enforcement in the proxy + `--allowed-tools` on CLI invocation (defense in depth). | `domain/mcp_proxy` + `plugins/claude_code.service` |
| 8 | Audit rows per JSON-RPC method (§5 shape). | `domain/mcp_proxy` |
| 9 | Reviewer-side wiring — write `.mcp.json` before CLI spawn, delete after review. | `plugins/claude_code.service` |
| 10 | Org settings UI — `/orgs/$slug/settings/integrations` — admin toggles which providers are enabled; users connect/disconnect per provider. | `domain/orgs` + `apps/web/src/domain/integrations` (new) |
| 11 | Per-org enable flag and per-server allowed-tools selection. | `domain/orgs.models` extension |
| 12 | Docs — new `domain_integrations.md`, new `domain_mcp_proxy.md`; updates to `system-architecture.md` for new outbound-auth flows. | `apps/backend/docs/`, `docs/` |

Rough effort: a milestone in its own right (future-milestone candidate). 2–3 weeks if scoped tight; longer if (B) below.

## 8. Open questions

### Q1. Webhook-triggered reviews — fallback identity

When the GitHub App webhook fires `pull_request.opened`, no human triggered the review. There is no user whose Linear creds the proxy can use. Choices:

- **(a) Author attribution.** If the PR's GitHub login is linked to a yaaos user who's connected Linear, use that user's creds. Fails silently for PRs from contributors without a yaaos account.
- **(b) Org service-account fallback.** Org admin connects a service-account Linear token at org scope; webhook reviews use it; human-triggered reviews still use the human's creds. Two-tier model.
- **(c) Defer.** Webhook review runs without MCP context; agent runs with diff only; a human can re-trigger with their attribution to get the enriched pass.

This decides whether `mcp_credentials` is keyed by `user_id` only or `(scope, scope_id)` where `scope ∈ {user, org}`. **(b)** is what most teams will actually want; **(a)** is fragile; **(c)** is the cheapest if you're willing to accept degraded webhook reviews.

### Q2. yaaos as OAuth-app owner vs PAT-paste

Per provider, two UX options for v1:

- **OAuth flow.** yaaos hosts the OAuth app, user clicks "Connect Linear", browser redirects through Linear, callback lands at yaaos, tokens stored. Best UX; correct token-lifecycle (rotation, scopes, revocation). Requires per-provider OAuth-app registration per yaaos instance (self-hosted: admin pastes client_id/secret into env; SaaS: yaaos hosts a central app).
- **PAT paste.** User generates a long-lived Personal Access Token in Linear's UI and pastes it into yaaos. Way less code (no OAuth flow per provider). Terrible UX, long-lived tokens, broader blast radius if leaked.

Recommendation: **OAuth from the start.** PAT paste accumulates as tech debt that's hard to remove; once users have PATs configured, migrating them to OAuth becomes a forced re-onboarding.

### Q3. Hosted MCP vs REST-shim per provider

Forward-path (use the upstream's hosted MCP) is way less code than REST-shim (implement the MCP server in yaaos). Recommendation: **hosted only for M03**; defer REST-shim to a follow-up if a high-priority provider doesn't have a hosted MCP yet. This scopes the initial provider list to:

- Linear (hosted: `mcp.linear.app/sse`)
- Notion (hosted: `mcp.notion.com/mcp`)
- GitHub (hosted: GitHub MCP server)
- Sentry (hosted MCP)
- Slack (hosted MCP)

Plenty to start with.

### Q4. What does the agent do when a tool isn't connected?

If a user hasn't connected Linear and the agent tries `tools/call name=get_issue`, the proxy should return a structured MCP error: `{"code": "not_connected", "message": "User has not connected Linear; the review continues without Linear context."}`. The agent's system prompt should describe how to handle that gracefully (don't loop; mention the missing context in the review output).

### Q5. Read vs write tool exposure

Linear/Notion/etc. MCPs expose both read and *write* tools (`update_issue`, `create_comment`, etc.). For an autonomous reviewer, almost certainly read-only by default. Allowlist lives on `mcp_credentials.allowed_tools` (text[]) per (user, provider) — users decide whether to grant write to yaaos's bot, off by default. Org-level cap: admin can constrain the per-user allowlist (e.g., "no write tools, ever, regardless of user preference").

## 9. Recommended phasing

If a future milestone scopes "MCP context for reviewer agents":

**Phase 1 — foundation (must ship together):**
- `mcp_credentials` table + outbound-OAuth flow for one provider (Linear is the obvious first).
- Per-`(user, provider)` refresh serialization.
- `mcp_review_tokens` table.
- The proxy route — forward-path only (no REST-shim yet).
- Reviewer-side `.mcp.json` materialization.
- Audit rows.
- Settings UI to connect/disconnect Linear.
- One open question resolved: **Q1 webhook-trigger fallback** must be decided before this phase ships.

**Phase 2 — second provider:**
- Notion (or GitHub or Sentry). Tests the per-provider abstraction; surfaces drift.

**Phase 3 — polish:**
- Per-tool allowlist UI.
- Org-level cap on per-user allowlist.
- Containerized workspace egress firewall (depends on the workspace-isolation milestone; may not land in M03).

**Explicitly out of scope:**
- REST-shim path (defer until a provider without hosted MCP becomes a priority).
- Per-repo overrides (different tools per repo).
- "Routed" context (PR-mention-driven server enable). Start static; observe; optimize.

## 10. Cross-links

- `plan/notes/full-pr-flow.md` — reviewer module re-architecture; this note's `mcp_review_tokens` and `.mcp.json` materialization slot into the review lifecycle described there.
- `plan/notes/security-posture.md` — the trust-boundary story; Pattern B is what makes the workspace-egress firewall plan tractable for tool access.
- `apps/backend/docs/plugins_oauth_github.md` — existing inbound-OAuth flow; outbound-OAuth in `domain/integrations` should mirror its shape (provider registry, ProviderProfile-style, settings-driven endpoint URLs for test-stack overrides).
