"""HMAC verification — pure helper, no DB or HTTP needed."""

import hashlib
import hmac

from app.plugins.github import verify_webhook_signature


def _sign(body: bytes, secret: bytes) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def test_valid_signature_passes() -> None:
    secret = b"super-secret"
    body = b'{"hello":"world"}'
    sig = _sign(body, secret)
    assert verify_webhook_signature(body, sig, secret) is True


def test_invalid_signature_fails() -> None:
    secret = b"super-secret"
    body = b'{"hello":"world"}'
    assert verify_webhook_signature(body, "sha256=deadbeef", secret) is False


def test_missing_header_fails() -> None:
    assert verify_webhook_signature(b"x", None, b"x") is False


def test_wrong_prefix_fails() -> None:
    assert verify_webhook_signature(b"x", "sha1=abc", b"x") is False
