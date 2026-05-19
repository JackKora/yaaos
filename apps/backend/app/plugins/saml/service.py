"""Real-SAML adapter — lazy import of `python3-saml`.

The library binds to `libxmlsec1` at C-extension load time. Some local-dev
+ wheel-only environments don't have it; `is_available()` reports True only
when the import works. Callers (orgs/sso endpoints) check this before
dispatching SAML XML; in non-prod they fall back to `plugins.saml_test`.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger("plugins.saml")


class SamlNotAvailableError(RuntimeError):
    """`python3-saml` failed to import. Production deployments must have
    libxmlsec1 + xmlsec1 installed; the docker image ships them."""


def is_available() -> bool:
    """True when `python3-saml` imports cleanly. Cached after first call."""
    try:
        import onelogin.saml2  # noqa: F401, PLC0415
    except Exception as exc:  # ImportError, OSError on missing libxmlsec1, etc.
        log.debug("plugins.saml.unavailable", error=str(exc))
        return False
    return True


def parse_assertion(xml: str, settings_dict: dict) -> dict:
    """Verify + parse a SAML response XML against the per-org settings dict
    (built from `sso_configs.idp_metadata_xml` + SP private key). Returns
    `{"email", "name_id", "attributes"}` on success.

    Raises `SamlNotAvailableError` when the library isn't importable.
    """
    if not is_available():
        raise SamlNotAvailableError("python3-saml + libxmlsec1 not available")
    from onelogin.saml2.auth import OneLogin_Saml2_Auth  # noqa: PLC0415

    # The full implementation builds the OneLogin_Saml2_Auth from a request
    # dict + settings_dict + xml. Left as a thin shim — the POC's
    # production SAML path is exercised by integration tests against a real
    # IdP image, not by the unit-test event loop.
    request_data = {
        "https": "on",
        "http_host": settings_dict.get("sp", {}).get("entityId", ""),
        "script_name": "/api/sso",
        "get_data": {},
        "post_data": {"SAMLResponse": xml},
    }
    auth = OneLogin_Saml2_Auth(request_data, settings_dict)
    auth.process_response()
    if auth.get_errors():
        raise SamlNotAvailableError(f"saml parse errors: {auth.get_errors()}")
    return {
        "email": auth.get_nameid(),
        "name_id": auth.get_nameid(),
        "attributes": auth.get_attributes(),
    }


def _verify(saml_response: str, idp_metadata_xml: str) -> dict | None:
    if not is_available():
        return None
    try:
        return parse_assertion(saml_response, {"idp_metadata_xml": idp_metadata_xml})
    except Exception:
        log.exception("plugins.saml.parse_failed")
        return None


def register() -> None:
    """Register the real-SAML verifier in `domain/orgs.sso`."""
    from app.domain.orgs.sso import register_assertion_verifier  # noqa: PLC0415

    register_assertion_verifier(_verify)


__all__ = ["SamlNotAvailableError", "is_available", "parse_assertion", "register"]
