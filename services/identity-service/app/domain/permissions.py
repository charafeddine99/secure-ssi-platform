from collections.abc import Iterable
from enum import StrEnum
from types import MappingProxyType

from app.domain.exceptions import InvalidRoleError


class Role(StrEnum):
    ADMIN = "admin"
    ISSUER = "issuer"
    VERIFIER = "verifier"
    HOLDER = "holder"


class Permission(StrEnum):
    AUTH_SELF_READ = "auth:self:read"
    CREDENTIALS_REVOKE = "credentials:revoke"
    CREDENTIALS_SIGN = "credentials:sign"
    CREDENTIALS_VALIDATE = "credentials:validate"
    CREDENTIALS_VERIFY = "credentials:verify"
    PRESENTATIONS_CREATE = "presentations:create"
    PRESENTATIONS_READ = "presentations:read"
    PRESENTATIONS_VERIFY = "presentations:verify"
    PRESENTATIONS_RECONCILE = "presentations:reconcile"
    WALLETS_CREATE = "wallets:create"
    WALLETS_READ = "wallets:read"
    WALLETS_CREDENTIALS_READ = "wallets:credentials:read"
    PRESENTATION_CHALLENGES_CREATE = "presentation-challenges:create"
    PRESENTATION_CHALLENGES_READ = "presentation-challenges:read"


_ROLE_PERMISSIONS = MappingProxyType(
    {
        Role.ADMIN: frozenset(Permission),
        Role.ISSUER: frozenset(Permission),
        Role.VERIFIER: frozenset(
            {
                Permission.CREDENTIALS_VALIDATE,
                Permission.CREDENTIALS_VERIFY,
                Permission.AUTH_SELF_READ,
                Permission.PRESENTATIONS_READ,
                Permission.PRESENTATIONS_VERIFY,
                Permission.PRESENTATION_CHALLENGES_CREATE,
                Permission.PRESENTATION_CHALLENGES_READ,
            }
        ),
        Role.HOLDER: frozenset(
            {
                Permission.AUTH_SELF_READ,
                Permission.PRESENTATIONS_CREATE,
                Permission.PRESENTATIONS_READ,
                Permission.WALLETS_CREATE,
                Permission.WALLETS_READ,
                Permission.WALLETS_CREDENTIALS_READ,
                Permission.PRESENTATION_CHALLENGES_READ,
            }
        ),
    }
)


def normalize_roles(values: Iterable[Role | str]) -> tuple[Role, ...]:
    normalized: set[Role] = set()
    for value in values:
        try:
            normalized.add(value if isinstance(value, Role) else Role(value))
        except ValueError as error:
            raise InvalidRoleError("Role is outside the local allowlist.") from error
    return tuple(role for role in Role if role in normalized)


def permissions_for_roles(
    roles: Iterable[Role | str],
) -> tuple[Permission, ...]:
    normalized = normalize_roles(roles)
    permissions = set().union(
        *(_ROLE_PERMISSIONS[role] for role in normalized),
    )
    return tuple(
        permission
        for permission in Permission
        if permission in permissions
    )
