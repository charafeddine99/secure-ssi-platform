from dataclasses import dataclass
from datetime import datetime

from app.domain.permissions import (
    Permission,
    Role,
    normalize_roles,
    permissions_for_roles,
)


@dataclass(frozen=True)
class User:
    id: str
    username: str
    display_name: str
    roles: tuple[Role, ...]
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.username or not self.display_name:
            raise ValueError("Public user fields must not be empty.")
        object.__setattr__(self, "roles", normalize_roles(self.roles))
        if not self.roles:
            raise ValueError("A local user must have at least one role.")


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    id: str
    username: str
    display_name: str
    roles: tuple[Role, ...]
    permissions: tuple[Permission, ...]
    authentication_source: str

    @classmethod
    def from_user(
        cls,
        user: User,
        *,
        authentication_source: str,
    ) -> "AuthenticatedPrincipal":
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            roles=normalize_roles(user.roles),
            permissions=permissions_for_roles(user.roles),
            authentication_source=authentication_source,
        )


@dataclass(frozen=True)
class TokenClaims:
    issuer: str
    subject: str
    audience: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    jwt_id: str
    roles: tuple[Role, ...]
    token_use: str

    def __post_init__(self) -> None:
        for value in (self.issued_at, self.not_before, self.expires_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Token claim times must be timezone-aware.")
        object.__setattr__(self, "roles", normalize_roles(self.roles))
