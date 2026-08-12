from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from app.domain.recovery import RecoveryAuthorizationError


class Role(StrEnum):
    ADMIN = "admin"
    ISSUER = "issuer"
    VERIFIER = "verifier"
    HOLDER = "holder"


class Permission(StrEnum):
    GUARDIAN_CREATE = "guardian:create"
    GUARDIAN_READ = "guardian:read"
    GUARDIAN_UPDATE = "guardian:update"
    GUARDIAN_REMOVE = "guardian:remove"
    RECOVERY_REQUEST_CREATE = "recovery:request:create"
    RECOVERY_REQUEST_READ = "recovery:request:read"
    RECOVERY_REQUEST_CANCEL = "recovery:request:cancel"
    RECOVERY_APPROVE = "recovery:approve"
    RECOVERY_REJECT = "recovery:reject"
    RECOVERY_POLICY_READ = "recovery:policy:read"
    RECOVERY_POLICY_UPDATE = "recovery:policy:update"
    RECOVERY_RECONCILE = "recovery:reconcile"


_HOLDER_PERMISSIONS = frozenset(
    {
        Permission.GUARDIAN_CREATE,
        Permission.GUARDIAN_READ,
        Permission.GUARDIAN_UPDATE,
        Permission.GUARDIAN_REMOVE,
        Permission.RECOVERY_REQUEST_CREATE,
        Permission.RECOVERY_REQUEST_READ,
        Permission.RECOVERY_REQUEST_CANCEL,
        Permission.RECOVERY_APPROVE,
        Permission.RECOVERY_REJECT,
        Permission.RECOVERY_POLICY_READ,
        Permission.RECOVERY_POLICY_UPDATE,
    }
)
_ROLE_PERMISSIONS = MappingProxyType(
    {
        Role.ADMIN: frozenset(Permission),
        Role.HOLDER: _HOLDER_PERMISSIONS,
        Role.ISSUER: frozenset(),
        Role.VERIFIER: frozenset(),
    }
)


@dataclass(frozen=True)
class RecoveryPrincipal:
    user_id: str
    roles: tuple[Role, ...]
    permissions: frozenset[Permission]

    @classmethod
    def from_claims(cls, user_id: str, roles: tuple[str, ...]) -> "RecoveryPrincipal":
        try:
            normalized = tuple(dict.fromkeys(Role(role) for role in roles))
        except ValueError as error:
            raise RecoveryAuthorizationError("Access token role is invalid.") from error
        if not user_id or not normalized:
            raise RecoveryAuthorizationError("Access token subject is invalid.")
        permissions = frozenset().union(*(_ROLE_PERMISSIONS[role] for role in normalized))
        return cls(user_id=user_id, roles=normalized, permissions=permissions)

    @property
    def is_admin(self) -> bool:
        return Role.ADMIN in self.roles

    def require(self, permission: Permission) -> None:
        if permission not in self.permissions:
            raise RecoveryAuthorizationError("Required recovery permission is missing.")
