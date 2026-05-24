"""Service entry-points for `domain/identity`.

Re-exports public types and exposes the login orchestrator that providers
call from the OAuth callback. The orchestrator owns the identity-binding
rules; provider plugins only produce a normalized `ProviderProfile`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.identity import repository as repo
from app.domain.identity.providers import ProviderProfile
from app.domain.identity.types import (
    EmailAlreadyLinkedError,
    OAuthIdentity,
    Session,
    SessionNotFoundError,
    TotpError,
    User,
    UserEmail,
    UserNotFoundError,
)

__all__ = [
    "EmailAlreadyLinkedError",
    "LoginResult",
    "OAuthIdentity",
    "Session",
    "SessionNotFoundError",
    "TotpError",
    "User",
    "UserEmail",
    "UserNotFoundError",
    "login_via_oauth",
]


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Outcome of OAuth login orchestration.

    `user is None` means the OAuth profile is verified but no yaaos user
    matches it — neither by `(provider, external_subject)` nor by primary
    email. The caller redirects to `/login?reason=not_provisioned` with no
    cookie set; the user must be invited (by email) before they can sign
    in. This rule prevents stale cookies + DB wipes from spawning orphan
    accounts that infinite-bounce post-login.
    """

    user: User | None
    newly_created: bool


async def login_via_oauth(
    db: AsyncSession,
    *,
    provider_id: str,
    profile: ProviderProfile,
) -> LoginResult:
    """Apply the two-rule policy for an OAuth profile:

      1. (provider, external_subject) already bound → load that user.
      2. Verified email matches an existing user → auto-link: insert
         oauth_identities, return that user.
      3. No match → return `LoginResult(user=None, ...)`. The caller
         redirects to `/login?reason=not_provisioned`. Provisioning is
         invitation-only; no auto-create.

    Unverified emails are rejected by the caller before this is invoked.
    """
    identity_row = await repo.find_oauth_identity(
        db, provider=provider_id, external_subject=profile.external_subject
    )
    if identity_row is not None:
        user_row = await repo.get_user(db, identity_row.user_id)
        assert user_row is not None
        if provider_id == "github" and profile.provider_login:
            await repo.set_user_github_username(
                db, user_id=user_row.id, github_username=profile.provider_login
            )
        return LoginResult(user=User.from_row(user_row), newly_created=False)

    existing_user_row = await repo.find_user_by_email(db, profile.primary_email)
    if existing_user_row is not None:
        await repo.add_oauth_identity(
            db,
            user_id=existing_user_row.id,
            provider=provider_id,
            external_subject=profile.external_subject,
        )
        if provider_id == "github" and profile.provider_login:
            await repo.set_user_github_username(
                db, user_id=existing_user_row.id, github_username=profile.provider_login
            )
        return LoginResult(user=User.from_row(existing_user_row), newly_created=False)

    return LoginResult(user=None, newly_created=False)
