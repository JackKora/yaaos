# fake-notion

Test-only fake Notion service. Implements just enough of Notion's OAuth +
hosted-MCP surface to drive yaaos M04 end-to-end without registering a real
Notion public integration.

## Emulated

- **OAuth 2.0** at `/v1/oauth/authorize` (auto-grants, no UI) and
  `/v1/oauth/token` (both `authorization_code` and `refresh_token`). Client
  authentication on the token endpoint uses HTTP Basic (Notion-specific
  quirk); the yaaos `IntegrationProvider` config encodes that so the
  difference doesn't leak into `domain/integrations` itself.
- **MCP Streamable HTTP** at `POST /mcp`. Returns plain JSON-RPC; no SSE
  upgrade. Supports `tools/list` + `tools/call`.
- **Read tools**: `search`, `query_database`, `retrieve_page`, `retrieve_block`.
- **Write tools**: `update_page`, `create_comment`.
- **Identity probe** at `GET /v1/users/me`.

## Test hook

`POST /__test/reset` clears all in-memory state back to defaults. yaaos's
e2e harness calls it as part of its reset chain.

## Hardcoded credentials

`app/test_secrets.py`. Production code never imports this; the test
docker-compose overrides yaaos's Notion OAuth env vars to match.

## What it does NOT emulate

- Notion's full REST API (no `/v1/pages`, `/v1/blocks` write surface
  outside the MCP tools).
- Real pagination, rate limits.
- Real Notion's block-tree mutation semantics.
- The full MCP tool set Notion ships in production — only what yaaos
  exercises is implemented.
