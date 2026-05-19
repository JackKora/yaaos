"""plugins/oauth_github — GitHub OAuth Provider implementation."""

from app.plugins.oauth_github.service import GitHubOAuthProvider, bootstrap

__all__ = ["GitHubOAuthProvider", "bootstrap"]

# Registration runs at import time.
bootstrap()
