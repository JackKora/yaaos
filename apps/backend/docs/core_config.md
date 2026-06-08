# core/config

> Boot-time configuration via pydantic-settings — env vars and `.env*` files into a single typed `Settings`.

## Scope

- Owns: `Settings` (pydantic `BaseSettings`), `get_settings()` cached singleton.
- Read-only and stateless. No HTTP routes, no tables.

## Why / invariants

**Required fields raise at construction** — `database_url`, `yaaos_encryption_key`, `redis_url`, `yaaos_public_origin` must be set; absence crashes boot immediately with a pydantic `ValidationError`.

**All sensitive fields are `SecretStr`** — `repr`, `model_dump`, and `model_dump_json` all render as `'**********'`. Call `.get_secret_value()` only at the byte boundary (Fernet construction, JWT sign, HTTP Authorization header). Verified by `test_secret_redaction.py`.

**`.env` file precedence** — `.env` → `.env.local` → `.env.dev` → `.env.dev.local`. Later overrides earlier; process env overrides all. `extra="ignore"` so unknown vars don't error.

**Cached singleton** — `Settings()` parses env on every call; `@cache` on `get_settings()` makes subsequent calls free. Tests monkeypatching env must call `get_settings.cache_clear()` afterward.

**`YAAOS_PUBLIC_ORIGIN`** — required. Full external origin of this backend deployment (scheme + host[:port], no path; e.g. `https://app.yaaos.cloud`). Boot fails with a `ValidationError` when unset. Two values derive from it as `computed_field` properties (so existing readers are unchanged): `yaaos_app_base_url` = the origin (public link base for OAuth callbacks, invitation/SAML/MCP URLs), and `yaaos_public_hostname` = its `netloc` (host[:port]), which `core/agent_gateway` validates against the `X-Yaaos-Audience` header. The derived hostname must match `hostFromURL(YAAOS_BACKEND_URL)` on the agent side — that's `url.Host`, so a port is preserved (e.g. `web:8080`); use `.netloc`, not `.hostname`.

## Gotchas

- Callers never instantiate `Settings` directly — always via `get_settings()`.
- `cors_origins_list` returns `["*"]` when `yaaos_env == "dev"`; otherwise parsed `YAAOS_CORS_ORIGINS`.

