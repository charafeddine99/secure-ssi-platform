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
    WALLET_KEY_CREATE = "wallet:key:create"
    WALLET_KEY_READ = "wallet:key:read"
    WALLET_KEY_ROTATE = "wallet:key:rotate"
    WALLET_KEY_SUSPEND = "wallet:key:suspend"
    WALLET_KEY_RESUME = "wallet:key:resume"
    WALLET_KEY_COMPROMISE = "wallet:key:compromise"
    WALLET_KEY_REVOKE = "wallet:key:revoke"
    WALLET_KEY_DESTROY = "wallet:key:destroy"
    WALLET_KEY_RECONCILE = "wallet:key:reconcile"
    ADMIN_KEY_RECONCILE = "admin:key:reconcile"


_ROLE_PERMISSIONS = MappingProxyType(
    {
        Role.ADMIN: frozenset(Permission),
        Role.ISSUER: frozenset(
            permission
            for permission in Permission
            if not permission.value.startswith(("wallet:key:", "admin:key:"))
        ),
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
                Permission.WALLET_KEY_CREATE,
                Permission.WALLET_KEY_READ,
                Permission.WALLET_KEY_ROTATE,
                Permission.WALLET_KEY_SUSPEND,
                Permission.WALLET_KEY_RESUME,
                Permission.WALLET_KEY_REVOKE,
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
