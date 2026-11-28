"""Organizations, memberships and capabilities, kept apart from user accounts.

User account != Organization != Membership != Issuer/Verifier capability != Holder.

- A user account is a person (``users`` collection, unchanged).
- An Organization is the institution: its legal name, type and verification status.
- A Membership links one account to one organization with organization roles; a person can belong to
  several organizations with different roles and is still a personal Holder at the same time.
- A Capability (ISSUER or VERIFIER) is what an organization may do in the SSI ecosystem. It is applied
  for and approved separately: a verified organization is not automatically an issuer or a verifier.
- Holder stays a property of the person's own wallet, not an organization role or a login type.

The W3C VC Data Model 2.0 names holder, issuer and verifier as roles any entity can play; how a
platform authorizes an organization to play them is its own decision, made here.
"""

from enum import StrEnum
from types import MappingProxyType


class OrganizationType(StrEnum):
    UNIVERSITY = "UNIVERSITY"
    GOVERNMENT = "GOVERNMENT"
    COMPANY = "COMPANY"
    NONPROFIT = "NONPROFIT"
    CERTIFICATION_BODY = "CERTIFICATION_BODY"
    OTHER_INSTITUTION = "OTHER_INSTITUTION"


class OrganizationStatus(StrEnum):
    SUBMITTED = "SUBMITTED"  # applied, waiting for a trust reviewer
    ACTIVE = "ACTIVE"  # entity and applicant's authority verified and approved
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"  # temporarily stopped; records and history stay
    REVOKED = "REVOKED"  # permanently stopped; records and history stay


class MembershipStatus(StrEnum):
    PENDING = "PENDING"  # the applicant, until the organization is approved
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class CapabilityType(StrEnum):
    ISSUER = "ISSUER"
    VERIFIER = "VERIFIER"


class CapabilityStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class OrgRole(StrEnum):
    ORG_ADMIN = "ORG_ADMIN"
    ISSUER_MANAGER = "ISSUER_MANAGER"
    ISSUER_OPERATOR = "ISSUER_OPERATOR"
    VERIFIER_MANAGER = "VERIFIER_MANAGER"
    VERIFIER_OPERATOR = "VERIFIER_OPERATOR"
    ORG_AUDITOR = "ORG_AUDITOR"


class OrgPermission(StrEnum):
    ORGANIZATION_READ = "organization:read"
    ORGANIZATION_MANAGE = "organization:manage"
    MEMBERSHIP_INVITE = "membership:invite"
    MEMBERSHIP_REMOVE = "membership:remove"
    MEMBERSHIP_ROLES_ASSIGN = "membership:roles:assign"
    ISSUER_CONFIGURE = "issuer:configure"
    CREDENTIAL_ISSUE = "credential:issue"
    CREDENTIAL_REVOKE = "credential:revoke"
    VERIFIER_CONFIGURE = "verifier:configure"
    PRESENTATION_VERIFY = "presentation:verify"
    AUDIT_READ = "audit:read"


_P = OrgPermission
ROLE_PERMISSIONS = MappingProxyType({
    # Organization administrators run the organization and its people. They do not issue or verify,
    # and they cannot approve their own organization's capabilities: that is a platform decision.
    OrgRole.ORG_ADMIN: frozenset({_P.ORGANIZATION_READ, _P.ORGANIZATION_MANAGE, _P.MEMBERSHIP_INVITE,
                                  _P.MEMBERSHIP_REMOVE, _P.MEMBERSHIP_ROLES_ASSIGN, _P.AUDIT_READ}),
    OrgRole.ISSUER_MANAGER: frozenset({_P.ORGANIZATION_READ, _P.ISSUER_CONFIGURE, _P.CREDENTIAL_ISSUE,
                                       _P.CREDENTIAL_REVOKE}),
    OrgRole.ISSUER_OPERATOR: frozenset({_P.ORGANIZATION_READ, _P.CREDENTIAL_ISSUE}),
    OrgRole.VERIFIER_MANAGER: frozenset({_P.ORGANIZATION_READ, _P.VERIFIER_CONFIGURE, _P.PRESENTATION_VERIFY}),
    OrgRole.VERIFIER_OPERATOR: frozenset({_P.ORGANIZATION_READ, _P.PRESENTATION_VERIFY}),
    OrgRole.ORG_AUDITOR: frozenset({_P.ORGANIZATION_READ, _P.AUDIT_READ}),
})

# Permissions that only make sense while the matching capability is ACTIVE.
CAPABILITY_FOR_PERMISSION = MappingProxyType({
    _P.ISSUER_CONFIGURE: CapabilityType.ISSUER,
    _P.CREDENTIAL_ISSUE: CapabilityType.ISSUER,
    _P.CREDENTIAL_REVOKE: CapabilityType.ISSUER,
    _P.VERIFIER_CONFIGURE: CapabilityType.VERIFIER,
    _P.PRESENTATION_VERIFY: CapabilityType.VERIFIER,
})


def permissions_for(roles: tuple[str, ...] | list[str]) -> frozenset[OrgPermission]:
    granted: set[OrgPermission] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(OrgRole(role), frozenset())
    return frozenset(granted)


def parse_roles(values: list[str] | tuple[str, ...]) -> tuple[OrgRole, ...]:
    """Server-side allowlist: unknown roles are refused, duplicates dropped, order fixed."""
    chosen = {OrgRole(value) for value in values}
    if not chosen:
        raise ValueError("At least one organization role is required.")
    return tuple(role for role in OrgRole if role in chosen)


class OrganizationError(Exception):
    """A controlled refusal in the organization model, with a safe code and HTTP status."""

    status_code = 400
    code = "ORGANIZATION_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class OrganizationNotFoundError(OrganizationError):
    """Also used for organizations the caller is not a member of, so nothing leaks across tenants."""

    status_code = 404
    code = "ORGANIZATION_NOT_FOUND"


class OrganizationForbiddenError(OrganizationError):
    status_code = 403
    code = "ORGANIZATION_PERMISSION_DENIED"


class OrganizationStateError(OrganizationError):
    status_code = 409
    code = "ORGANIZATION_STATE_CONFLICT"


class InvitationInvalidError(OrganizationError):
    status_code = 400
    code = "INVITATION_INVALID"
