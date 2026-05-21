# plugins/linear

> `IntegrationProvider` for Linear — OAuth + hosted MCP wiring.

## Purpose

Lets an org connect its Linear workspace so the reviewer agent can fetch issue context via hosted MCP. Implements `domain/integrations.IntegrationProvider`: declares the `ProviderConfig` (OAuth + MCP URLs + tool catalogue) and a thin `validate(access_token)` that hits Linear's `/api/me`.

## Public interface

- `LinearProvider` — concrete `IntegrationProvider`. `provider_id = "linear"`.
- `bootstrap()` — `domain/integrations.register_provider(_provider)` at import time. Skips when `yaaos_oauth_linear_client_id` or `_client_secret` is unset.

No HTTP routes; the proxy + OAuth callback live in [`domain/integrations`](domain_integrations.md).

## Module architecture

### Provider config

`ProviderConfig` from `core/oauth`:

- `authorize_url`, `token_url`, `refresh_url` — settings-driven; production defaults to `https://linear.app/oauth/...`. Test stacks point at `apps/fake-linear`.
- `mcp_url` — `https://mcp.linear.app/sse` in prod. The proxy POSTs JSON-RPC here with `Authorization: Bearer <upstream-access-token>`.
- `scope_separator = ","`, `default_scopes = ("read",)`.
- `token_auth_style = "form"` — client credentials in the token-endpoint form body.
- `known_read_tools = ("get_issue", "search_issues", "list_projects", "list_cycles")`. Always allowed by the proxy.
- `known_write_tools = ("update_issue", "create_comment")`. Allowed only when the org's `allowed_tools` lists them.

### Validate

`validate(access_token)` calls `GET /api/me` with `Authorization: Bearer <token>`; returns True on 2xx, False otherwise. The hourly health-check + manual "Test connection" both run this.

## Data owned

None. `mcp_credentials` lives in [`domain/integrations`](domain_integrations.md).

## How it's tested

Test stack runs `apps/fake-linear` in docker-compose so the OAuth + MCP round-trips exercise real HTTP. Backend integration tests in `app/domain/integrations/test/` use a stubbed `IntegrationProvider` for fast cases; the e2e suite drives the fake.
