"""domain/identity — users, emails, OAuth identities, sessions, TOTP."""

from app.domain.identity import repository, sessions, totp
from app.domain.identity.models import OAuthIdentityRow, SessionRow, UserEmailRow, UserRow
from app.domain.identity.providers import (
    ProviderError,
    ProviderProfile,
    get_provider,
    list_providers,
    register_provider,
)
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
    login_via_oauth,
)
from app.domain.identity.totp import can_be_sso_exempt_owner, has_verified_totp

# NOTE: `identity.user_web` and `identity.web` are not imported here to avoid
# circular imports at load time. They appear in `__all__` so tach allows
# side-effect imports from other modules.

__all__ = [
    "EmailAlreadyLinkedError",
    "OAuthIdentity",
    "OAuthIdentityRow",
    "ProviderError",
    "ProviderProfile",
    "Session",
    "SessionNotFoundError",
    "SessionRow",
    "TotpError",
    "User",
    "UserEmail",
    "UserEmailRow",
    "UserNotFoundError",
    "UserRow",
    "can_be_sso_exempt_owner",
    "create_email",
    "create_oauth_identity",
    "create_session",
    "create_user",
    "get_provider",
    "has_verified_totp",
    "list_providers",
    "login_via_oauth",
    "register_provider",
    "repository",
    "service",
    "sessions",
    "totp",
    "user_web",
    "web",
]
