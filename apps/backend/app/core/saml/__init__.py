"""core/saml — generic SAML SP primitives: keypair, assertion verification, metadata."""

from app.core.saml.service import (
    SamlNotAvailableError,
    generate_sp_keypair,
    is_available,
    parse_assertion,
    verify_assertion,
)

__all__ = [
    "SamlNotAvailableError",
    "generate_sp_keypair",
    "is_available",
    "parse_assertion",
    "verify_assertion",
]
