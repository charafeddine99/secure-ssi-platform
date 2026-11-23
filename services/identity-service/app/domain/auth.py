from dataclasses import dataclass
from datetime import datetime

from app.domain.permissions import (
    Permission,
    Role,
    normalize_roles,
    permissions_for_roles,
)


def _normalize_issuer_did(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > 2_048
        or len(normalized) <= len("did:web:")
        or not normalized.startswith("did:web:")
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError("Issuer scope must be a valid did:web identifier.")
    return normalized


@dataclass(frozen=True)
class User:
    id: str
    username: str
    display_name: str
    roles: tuple[Role, ...]
    enabled: bool = True
    issuer_did: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.username or not self.display_name:
            raise ValueError("Public user fields must not be empty.")
        object.__setattr__(self, "roles", normalize_roles(self.roles))
        if not self.roles:
            raise ValueError("A local user must have at least one role.")
        issuer_did = _normalize_issuer_did(self.issuer_did)
        if issuer_did is not None and Role.ISSUER not in self.roles:
            raise ValueError("Issuer scope can only be assigned to an issuer role.")
        object.__setattr__(self, "issuer_did", issuer_did)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    id: str
    username: str
    display_name: str
    roles: tuple[Role, ...]
    permissions: tuple[Permission, ...]
    authentication_source: str
    issuer_did: str | None = None
    session_id: str = ""

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
            issuer_did=user.issuer_did,
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
