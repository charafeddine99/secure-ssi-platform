from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission, Role
from app.schemas.credential_api import ApiModel


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def username_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username must not be blank.")
        return normalized


class PublicUserResponse(ApiModel):
    id: str
    username: str
    display_name: str
    roles: list[Role]
    permissions: list[Permission]

    @classmethod
    def from_principal(
        cls,
        principal: AuthenticatedPrincipal,
    ) -> "PublicUserResponse":
        return cls(
            id=principal.id,
            username=principal.username,
            display_name=principal.display_name,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
        )


class TokenResponse(ApiModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    user: PublicUserResponse


class CurrentUserResponse(PublicUserResponse):
    authentication_source: Literal["local-synthetic-fixture"]

    @classmethod
    def from_principal(
        cls,
        principal: AuthenticatedPrincipal,
    ) -> "CurrentUserResponse":
        return cls(
            id=principal.id,
            username=principal.username,
            display_name=principal.display_name,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
            authentication_source="local-synthetic-fixture",
        )
