"""Generic OAuth 2.0 authorization-code + refresh primitives.

Three top-level functions:

- `build_authorize_url(config, state, scopes, redirect_uri)` — return the URL the
  user agent should be 302'd to. Pure string-building; no I/O.
- `exchange_code(config, code, redirect_uri)` — POST the token endpoint. Returns
  a `Tokens` value object (access + optional refresh + expires_in + scope).
- `refresh_access_token(config, refresh_token)` — POST the refresh endpoint.
  Returns the same `Tokens` shape; many providers rotate refresh tokens, so
  callers persist the new refresh value when it changes.

Provider-specific quirks (scope separator, token-endpoint auth style: form vs
HTTP Basic) live in `ProviderConfig`. Anything beyond the OAuth dance —
persistence, signing of `state`, audit emission — is the caller's job.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import structlog
from pydantic import SecretStr

log = structlog.get_logger("core.oauth")


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """OAuth + MCP wiring for one upstream provider.

    Provider plugins fill this in at bootstrap. Env-var overrides
    (`LINEAR_OAUTH_AUTHORIZE_URL` etc.) let the test compose swap in the
    local fakes; production defaults are the real upstream URLs.

    Lives here in `core/oauth` rather than `domain/integrations` because
    `core/oauth.exchange_code` consumes it — `core` can't import `domain`.
    """

    authorize_url: str
    token_url: str
    refresh_url: str
    mcp_url: str
    client_id: str
    client_secret: SecretStr
    scope_separator: str  # " " for most; commas for some
    default_scopes: tuple[str, ...]
    known_read_tools: tuple[str, ...]
    known_write_tools: tuple[str, ...]
    # "form" (default — body-encoded client creds) or "basic" (HTTP Basic, à la Notion).
    token_auth_style: Literal["form", "basic"] = "form"


_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class Tokens:
    """OAuth token-endpoint response, normalized.

    `refresh_token` may be `None` for providers that don't issue refresh
    tokens. `expires_in` is seconds-from-now; the caller turns it into an
    absolute `expires_at` when persisting.
    """

    access_token: SecretStr
    refresh_token: SecretStr | None
    expires_in: int
    scope: str
    raw: dict[str, Any]


class OAuthError(RuntimeError):
    """Token-endpoint or transport failure. Caller surfaces to user."""


def build_authorize_url(
    config: ProviderConfig,
    *,
    state: str,
    redirect_uri: str,
    scopes: list[str] | None = None,
) -> str:
    """Build the URL we 302 the user to. `scopes=None` uses `config.default_scopes`."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": config.scope_separator.join(scopes or config.default_scopes),
    }
    sep = "&" if "?" in config.authorize_url else "?"
    return f"{config.authorize_url}{sep}{urlencode(params)}"


async def exchange_code(
    config: ProviderConfig,
    *,
    code: str,
    redirect_uri: str,
) -> Tokens:
    """Exchange an authorization code for tokens."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    return await _post_token(config, data)


async def refresh_access_token(
    config: ProviderConfig,
    *,
    refresh_token: SecretStr,
) -> Tokens:
    """Exchange a refresh token for a new access token (+ possibly rotated refresh)."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token.get_secret_value(),
    }
    return await _post_token(config, data, refresh_url=True)


async def _post_token(
    config: ProviderConfig,
    data: dict[str, str],
    *,
    refresh_url: bool = False,
) -> Tokens:
    url = config.refresh_url if refresh_url else config.token_url
    headers = {"Accept": "application/json"}

    # Provider-specific client-auth style: Notion uses HTTP Basic for the
    # token endpoint; Linear (and most others) accept form-encoded client_id
    # + client_secret. `ProviderConfig.token_auth_style` decides.
    if config.token_auth_style == "basic":
        creds = f"{config.client_id}:{config.client_secret.get_secret_value()}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(creds).decode()
    else:
        data = {
            **data,
            "client_id": config.client_id,
            "client_secret": config.client_secret.get_secret_value(),
        }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
            resp = await http.post(url, data=data, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("oauth.transport_error", url=url, error=str(exc))
        raise OAuthError(f"transport error: {exc}") from exc

    if resp.status_code != 200:
        log.warning("oauth.non_200", url=url, status=resp.status_code, body=resp.text[:300])
        raise OAuthError(f"token endpoint returned {resp.status_code}")
    try:
        body = resp.json()
    except ValueError as exc:
        raise OAuthError(f"non-json token response: {exc}") from exc

    access = body.get("access_token")
    if not access:
        raise OAuthError("missing access_token in response")
    refresh = body.get("refresh_token")
    return Tokens(
        access_token=SecretStr(access),
        refresh_token=SecretStr(refresh) if refresh else None,
        expires_in=int(body.get("expires_in") or 3600),
        scope=body.get("scope") or "",
        raw=body,
    )
