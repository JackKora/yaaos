"""domain/mcp_proxy — per-review MCP bearer + proxy."""

from app.domain.mcp_proxy.models import McpReviewTokenRow
from app.domain.mcp_proxy.service import (
    REVIEW_TOKEN_TTL,
    McpToken,
    _hash,
    consume_broken_creds,
    lookup_token,
    mint_token,
    record_broken_creds,
    revoke_token,
    sweep_expired,
)

# NOTE: `mcp_proxy.web` is not imported here to avoid potential circular imports.
# It appears in `__all__` so tach allows side-effect imports from other modules.

__all__ = [
    "REVIEW_TOKEN_TTL",
    "McpReviewTokenRow",
    "McpToken",
    "_hash",
    "consume_broken_creds",
    "lookup_token",
    "mint_token",
    "record_broken_creds",
    "revoke_token",
    "sweep_expired",
    "web",
]
