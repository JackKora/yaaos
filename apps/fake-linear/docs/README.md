# fake-linear

Test-only fake Linear service. Implements just enough of Linear's OAuth +
hosted-MCP surface to drive yaaos M04 end-to-end without registering a real
Linear OAuth app.

## Emulated

- **OAuth 2.0** at `/oauth/authorize` (auto-grants, no UI) and `/oauth/token`
  (both `authorization_code` and `refresh_token` grant types). Refresh tokens
  are **rotated** on each refresh — yaaos exercises this path.
- **MCP Streamable HTTP** at `POST /sse`. Returns plain JSON-RPC; no SSE
  upgrade. Supports `tools/list` + `tools/call`.
- **Read tools**: `get_issue`, `search_issues`, `list_projects`, `list_cycles`.
- **Write tools**: `update_issue`, `create_comment`.
- **Identity probe** at `GET /api/me` (used by the `validate()` callable).

## Test hook

`POST /__test/reset` clears all in-memory state (issues, comments, tokens,
pending codes) back to defaults. The yaaos e2e harness calls it as part of
its reset chain.

## Hardcoded credentials

`app/test_secrets.py`. Production code never imports this; the test
docker-compose overrides yaaos's Linear OAuth env vars to match.

## What it does NOT emulate

- Linear's GraphQL API (no REST/GraphQL outside the MCP tools).
- Real rate limits / pagination.
- Webhooks.
- The full set of MCP tools Linear ships in production — only what yaaos
  exercises is implemented.
