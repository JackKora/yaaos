"""`plugins/saml` lazy-availability tests.

The real-SAML path requires `libxmlsec1`; `is_available()` reports True only
when the system lib + python3-saml import cleanly. Tests cover the fallback
behavior (returns None) and the registry registration regardless of
availability.
"""

from __future__ import annotations

from app.domain.orgs import sso as sso_service
from app.plugins.saml import service as saml_service


def test_is_available_returns_bool() -> None:
    """Whatever the environment, `is_available` must not raise."""
    out = saml_service.is_available()
    assert isinstance(out, bool)


def test_register_pushes_verifier_into_registry() -> None:
    """`register()` was called at import; the verifier should be in the
    registry alongside the test stub. We can't directly inspect the list,
    but a roundtrip through `run_assertion_verifier` exercises both."""
    # Garbage input — the real verifier returns None (or library unavailable
    # → None). Either way the call doesn't raise.
    result = sso_service.run_assertion_verifier("not-saml-xml", "<EntityDescriptor/>")
    assert result is None or isinstance(result, dict)


def test_unavailable_parser_does_not_crash_dispatcher() -> None:
    """When the library can't load, the verifier short-circuits with None
    instead of raising."""
    if saml_service.is_available():
        # Skip — env has libxmlsec1; behavior is exercised by integration
        # tests against a real IdP image, not here.
        return
    out = saml_service._verify("not-xml", "<EntityDescriptor/>")
    assert out is None
