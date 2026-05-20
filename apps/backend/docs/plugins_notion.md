# plugins/notion

> `IntegrationProvider` for Notion — OAuth + hosted MCP wiring.

## Purpose

Lets an org connect its Notion workspace so the reviewer agent can pull page/doc context via hosted MCP. Same shape as [`plugins/linear`](plugins_linear.md); the differences are Notion-specific OAuth quirks.

## Public interface

- `NotionProvider` — concrete `IntegrationProvider`. `provider_id = "notion"`.
- `bootstrap()` — `domain/integrations.register_provider(_provider)` at import time. Skips when `yaaos_oauth_notion_client_id` or `_client_secret` is unset.

## Module architecture

### Provider config

`ProviderConfig` from `core/oauth`:

- `authorize_url`, `token_url`, `refresh_url` — settings-driven; production defaults to `https://api.notion.com/v1/oauth/...`.
- `mcp_url` — `https://mcp.notion.com/mcp` in prod.
- `scope_separator = " "` (URL-space), `default_scopes = ()` — Notion treats scope as fixed-per-app rather than per-request.
- `token_auth_style = "basic"` — **Notion quirk.** The token endpoint authenticates the app via HTTP Basic instead of form-body credentials. The `core/oauth._post_token` switch handles both.
- `known_read_tools = ("search", "query_database", "retrieve_page", "retrieve_block")`.
- `known_write_tools = ("update_page", "create_comment")`.

### Validate

`validate(access_token)` calls `GET /v1/users/me` with `Authorization: Bearer <token>` and the `Notion-Version: 2022-06-28` header that Notion requires on every API call.

## Data owned

None. `mcp_credentials` lives in [`domain/integrations`](domain_integrations.md).

## How it's tested

`apps/fake-notion` in docker-compose mirrors the Notion OAuth + MCP surface (HTTP Basic on token, `Notion-Version` header expectation, search/page/block/comment tools). Backend integration tests use a stubbed provider; e2e drives the fake.
