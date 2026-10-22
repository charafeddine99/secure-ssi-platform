from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class AdminUserApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class AdminUserResponse(AdminUserApiModel):
    id: str
    username: str
    display_name: str
    roles: list[str]
    enabled: bool
    issuer_did: str | None = None
    issuer_organization_name: str | None = None
    version: int


class IssuerScopeOptionResponse(AdminUserApiModel):
    issuer_did: str
    organization_name: str


class UpdateIssuerScopeRequest(AdminUserApiModel):
    issuer_did: str | None
    expected_version: int = Field(ge=1)
