"""plugins/saml — real SAML adapter via python3-saml.

This module is a thin wrapper that lazy-imports `python3-saml`. The library
needs `libxmlsec1` + `xmlsec1` system packages (installed in
`docker/Dockerfile`). When those are missing (some local-dev or wheel-only
environments), `is_available()` returns False and the orgs/sso endpoints
fall back to `plugins.saml_test` for the test stack.

Production: the docker image ships libxmlsec1; `is_available()` is True.
"""

from app.plugins.saml.service import (
    SamlNotAvailableError,
    is_available,
    parse_assertion,
    register,
)

__all__ = ["SamlNotAvailableError", "is_available", "parse_assertion", "register"]

register()
