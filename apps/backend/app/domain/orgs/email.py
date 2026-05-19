"""Minimal SMTP sender used by `domain/orgs` for invitation emails.

Dev points at Mailpit (`smtp://localhost:1025`); prod points at whatever SMTP
relay the operator configured. Synchronous `smtplib` wrapped in
`asyncio.to_thread` — invitation volume is low and `aiosmtplib` would only
add a dep for no real win.

Test mode (`yaaos_env == "test"`) short-circuits the send and accumulates
the message into a process-global list. Tests assert against that list.
"""

from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class SentEmail:
    to: str
    subject: str
    body: str


@dataclass
class _Inbox:
    """Captures emails in `test` env. Tests read + reset by clearing the list."""

    messages: list[SentEmail] = field(default_factory=list)


_test_inbox = _Inbox()


def get_test_inbox() -> list[SentEmail]:
    """Return the in-memory list of emails captured when `yaaos_env == "test"`.

    The list is mutated in place — tests clear it via `.clear()` between cases.
    """
    return _test_inbox.messages


def _send_blocking(msg: EmailMessage) -> None:
    s = get_settings()
    smtp = (
        smtplib.SMTP_SSL(s.smtp_host, s.smtp_port)
        if s.smtp_use_tls
        else smtplib.SMTP(s.smtp_host, s.smtp_port)
    )
    try:
        if s.smtp_username:
            smtp.login(s.smtp_username, s.smtp_password)
        smtp.send_message(msg)
    finally:
        smtp.quit()


async def send_plain(*, to: str, subject: str, body: str) -> None:
    """Send a plain-text email. In `test` env, append to the in-memory inbox
    and skip the SMTP round-trip; tests assert against `get_test_inbox()`."""
    settings = get_settings()
    if settings.yaaos_env == "test":
        _test_inbox.messages.append(SentEmail(to=to, subject=subject, body=body))
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    await asyncio.to_thread(_send_blocking, msg)


__all__ = ["SentEmail", "get_test_inbox", "send_plain"]
