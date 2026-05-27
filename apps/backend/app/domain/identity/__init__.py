"""domain/identity — users, emails, OAuth identities, sessions, TOTP."""

from app.domain.identity import sessions, web
from app.domain.identity.service import (
    EmailAlreadyLinkedError,
    OAuthIdentity,
    Session,
    SessionNotFoundError,
    TotpError,
    User,
    UserEmail,
    UserNotFoundError,
    create_email,
    create_oauth_identity,
    create_session,
    create_user,
)

__all__ = [
    "EmailAlreadyLinkedError",
    "OAuthIdentity",
    "Session",
    "SessionNotFoundError",
    "TotpError",
    "User",
    "UserEmail",
    "UserNotFoundError",
    "create_email",
    "create_oauth_identity",
    "create_session",
    "create_user",
    "sessions",
    "web",
]
