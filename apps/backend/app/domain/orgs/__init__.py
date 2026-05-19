"""domain/orgs — orgs, memberships, invitations, SSO config."""

from app.domain.orgs.invitations import (
    InvitationExpiredError,
    InvitationInvalidError,
    InvitationUsedError,
    accept_invitation,
    change_role,
    invite,
    remove_member,
)
from app.domain.orgs.models import (
    InvitationRow,
    MembershipRow,
    OrgRow,
    SsoConfigRow,
)
from app.domain.orgs.service import (
    InsufficientRoleError,
    Invitation,
    InvitationError,
    Membership,
    MembershipNotFoundError,
    Org,
    OrgNotFoundError,
    Role,
    SsoConfig,
)

# NOTE: `orgs.web` is registered from `main.py` (after `domain.auth` loads),
# not here — importing it from this __init__ would cycle through
# `domain.auth.dependencies`, which imports from `domain.orgs`.

__all__ = [
    "InsufficientRoleError",
    "Invitation",
    "InvitationError",
    "InvitationExpiredError",
    "InvitationInvalidError",
    "InvitationRow",
    "InvitationUsedError",
    "Membership",
    "MembershipNotFoundError",
    "MembershipRow",
    "Org",
    "OrgNotFoundError",
    "OrgRow",
    "Role",
    "SsoConfig",
    "SsoConfigRow",
    "accept_invitation",
    "change_role",
    "invite",
    "remove_member",
]
