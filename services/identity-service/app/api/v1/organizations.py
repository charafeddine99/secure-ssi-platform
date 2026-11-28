"""Organization applications, memberships, invitations, capabilities and platform trust review.

The organization a request acts on is always taken from the path and re-checked against the caller's stored
membership (OrganizationService.access); the client never supplies roles, user ids or tenant context that
the server trusts.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_auth_settings,
    get_clock,
    get_current_principal,
    get_mongo_connection_manager,
    get_step_up_service,
    require_permission,
)
from app.application.ports.repositories import AuditEventRepository
from app.application.services.organization_service import OrganizationService
from app.application.services.step_up_service import StepUpService
from app.config.environment_policy import is_production_like
from app.domain.auth import AuthenticatedPrincipal
from app.domain.organization import OrganizationError
from app.domain.permissions import Permission
from app.domain.persistence import AuditEvent, AuditEventType
from app.infrastructure.persistence.mappers import new_object_id
from app.schemas.credential_api import ApiModel

_LOGGER = logging.getLogger(__name__)
router = APIRouter(tags=["organizations"])
_ORG = r"^org_[A-Za-z0-9_-]{8,40}$"
_MEM = r"^mem_[A-Za-z0-9_-]{8,40}$"
_INV = r"^inv_[A-Za-z0-9_-]{8,40}$"
_CAP = r"^cap_[A-Za-z0-9_-]{8,40}$"
_EMAIL = r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$"
Text = Annotated[str, Field(min_length=2, max_length=500)]


async def organization_error_handler(request: Request, error: Exception) -> JSONResponse:
    from app.api.v1.error_handlers import build_error_response

    assert isinstance(error, OrganizationError)
    return build_error_response(request_id=getattr(request.state, "request_id", "unavailable"),
                                status_code=error.status_code, code=error.code, message=error.message,
                                headers={"Cache-Control": "no-store"})


def get_organization_service(
    manager: Any = Depends(get_mongo_connection_manager),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
    settings: Any = Depends(get_auth_settings),
    clock: Any = Depends(get_clock),
) -> OrganizationService:
    def record(event_type: str, subject: str, actor: str, metadata: dict[str, str]) -> None:
        now = datetime.now(UTC)
        try:
            audit_events.append(AuditEvent(
                id=new_object_id(), event_type=AuditEventType(event_type), subject_id=subject, actor_id=actor,
                correlation_id=None, metadata=metadata, created_at=now, updated_at=now, version=1))
        except Exception as error:  # noqa: BLE001 - an audit write must not undo the decision
            _LOGGER.warning("Organization audit event was not written (%s)", type(error).__name__)

    return OrganizationService(manager.database, clock=clock, record=record,
                               production=is_production_like(settings.environment))


# ------------------------------------------------------------------ response shapes
class MembershipView(ApiModel):
    membership_id: str
    user_id: str
    roles: list[str]
    status: str
    accepted_at: datetime | None = None


class OrganizationView(ApiModel):
    organization_id: str
    legal_name: str
    organization_type: str
    jurisdiction: str
    registration_reference: str | None
    official_domain: str | None
    website: str | None
    status: str
    requested_capabilities: list[str]
    created_at: datetime


class MyOrganizationView(ApiModel):
    organization: OrganizationView
    membership: MembershipView


class InvitationView(ApiModel):
    invitation_id: str
    email: str
    roles: list[str]
    status: str
    expires_at: datetime


class InvitationCreated(ApiModel):
    invitation: InvitationView
    invitation_code: str


class CapabilityView(ApiModel):
    capability_id: str
    organization_id: str
    type: str
    status: str
    credential_types: list[str]
    purpose: str
    issuer_did: str | None = None
    client_id: str | None = None
    redirect_uris: list[str] | None = None


class ReviewItem(ApiModel):
    organization: OrganizationView
    applicant_user_id: str
    applicant_title: str
    authority_evidence: str
    official_contact: str
    intended_use: str


def _org(row: dict[str, Any]) -> OrganizationView:
    return OrganizationView(
        organization_id=row["_id"], legal_name=row["legalName"], organization_type=row["organizationType"],
        jurisdiction=row["jurisdiction"], registration_reference=row.get("registrationReference"),
        official_domain=row.get("officialDomain"), website=row.get("website"), status=row["status"],
        requested_capabilities=row.get("application", {}).get("requestedCapabilities", []),
        created_at=row["createdAt"])


def _mem(row: dict[str, Any]) -> MembershipView:
    return MembershipView(membership_id=row["_id"], user_id=row["userId"], roles=row["roles"],
                          status=row["status"], accepted_at=row.get("acceptedAt"))


def _inv(row: dict[str, Any]) -> InvitationView:
    return InvitationView(invitation_id=row["_id"], email=row["email"], roles=row["roles"], status=row["status"],
                          expires_at=row["expiresAt"])


def _cap(row: dict[str, Any]) -> CapabilityView:
    details = row.get("details", {})
    return CapabilityView(capability_id=row["_id"], organization_id=row["organizationId"], type=row["type"],
                          status=row["status"], credential_types=details.get("credentialTypes", []),
                          purpose=details.get("purpose", ""), issuer_did=details.get("issuerDid"),
                          client_id=details.get("clientId"), redirect_uris=details.get("redirectUris"))


# ------------------------------------------------------------------ requests
class ApplicationRequest(ApiModel):
    legal_name: str = Field(min_length=2, max_length=300)
    organization_type: Literal["UNIVERSITY", "GOVERNMENT", "COMPANY", "NONPROFIT", "CERTIFICATION_BODY",
                               "OTHER_INSTITUTION"]
    jurisdiction: str = Field(min_length=2, max_length=100)
    registration_reference: str | None = Field(default=None, max_length=200)
    official_domain: str | None = Field(default=None, max_length=253, pattern=r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    website: str | None = Field(default=None, max_length=500, pattern=r"^https?://\S+$")
    official_contact: Text
    applicant_title: Text
    authority_evidence: Text
    requested_capabilities: list[Literal["ISSUER", "VERIFIER"]] = Field(default_factory=list, max_length=2)
    intended_use: Text


class InviteRequest(ApiModel):
    email: str = Field(pattern=_EMAIL, max_length=254)
    roles: list[str] = Field(min_length=1, max_length=6)


class AcceptRequest(ApiModel):
    invitation_code: str = Field(min_length=20, max_length=200)


class RolesRequest(ApiModel):
    roles: list[str] = Field(min_length=1, max_length=6)


class CapabilityRequest(ApiModel):
    type: Literal["ISSUER", "VERIFIER"]
    credential_types: list[str] = Field(min_length=1, max_length=20)
    purpose: Text
    issuer_did: str | None = Field(default=None, max_length=2048)
    client_id: str | None = Field(default=None, max_length=200)
    redirect_uris: list[str] | None = Field(default=None, max_length=10)


class OrganizationDecision(ApiModel):
    decision: Literal["APPROVE", "REJECT", "SUSPEND", "REINSTATE", "REVOKE"]
    entity_verified: bool = False
    entity_evidence: str = Field(default="", max_length=1000)
    representative_verified: bool = False
    representative_evidence: str = Field(default="", max_length=1000)
    note: Text


class CapabilityDecision(ApiModel):
    decision: Literal["APPROVE", "REJECT", "SUSPEND", "REINSTATE", "REVOKE"]
    note: Text


Principal = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]
Service = Annotated[OrganizationService, Depends(get_organization_service)]
OrgId = Annotated[str, Path(pattern=_ORG)]


# ------------------------------------------------------------------ member-facing routes
@router.post("/organizations/applications", response_model=OrganizationView, status_code=201)
def apply_for_organization(payload: ApplicationRequest, principal: Principal, service: Service) -> OrganizationView:
    return _org(service.apply(principal, **payload.model_dump(by_alias=False)))


@router.get("/organizations/mine", response_model=list[MyOrganizationView])
def my_organizations(principal: Principal, service: Service, response: Response) -> list[MyOrganizationView]:
    response.headers["Cache-Control"] = "no-store"
    return [MyOrganizationView(organization=_org(item["organization"]), membership=_mem(item["membership"]))
            for item in service.my_organizations(principal)]


@router.get("/organizations/{organization_id}", response_model=OrganizationView)
def read_organization(organization_id: OrgId, principal: Principal, service: Service) -> OrganizationView:
    return _org(service.get(principal, organization_id))


@router.get("/organizations/{organization_id}/members", response_model=list[MembershipView])
def list_members(organization_id: OrgId, principal: Principal, service: Service) -> list[MembershipView]:
    return [_mem(row) for row in service.members(principal, organization_id)]


@router.put("/organizations/{organization_id}/members/{membership_id}/roles", response_model=MembershipView)
def change_roles(organization_id: OrgId, membership_id: Annotated[str, Path(pattern=_MEM)],
                 payload: RolesRequest, principal: Principal, service: Service) -> MembershipView:
    return _mem(service.set_roles(principal, organization_id, membership_id, payload.roles))


@router.delete("/organizations/{organization_id}/members/{membership_id}", status_code=204)
def remove_member(organization_id: OrgId, membership_id: Annotated[str, Path(pattern=_MEM)],
                  principal: Principal, service: Service) -> Response:
    service.remove_member(principal, organization_id, membership_id)
    return Response(status_code=204)


@router.post("/organizations/{organization_id}/invitations", response_model=InvitationCreated, status_code=201)
def invite_member(organization_id: OrgId, payload: InviteRequest, principal: Principal, service: Service,
                  response: Response) -> InvitationCreated:
    """The code is shown once and only its digest is stored; send it to the person yourself."""
    code, invitation = service.invite(principal, organization_id, payload.email, payload.roles)
    response.headers["Cache-Control"] = "no-store"
    return InvitationCreated(invitation=_inv(invitation), invitation_code=code)


@router.get("/organizations/{organization_id}/invitations", response_model=list[InvitationView])
def list_invitations(organization_id: OrgId, principal: Principal, service: Service) -> list[InvitationView]:
    return [_inv(row) for row in service.invitations(principal, organization_id)]


@router.delete("/organizations/{organization_id}/invitations/{invitation_id}", status_code=204)
def revoke_invitation(organization_id: OrgId, invitation_id: Annotated[str, Path(pattern=_INV)],
                      principal: Principal, service: Service) -> Response:
    service.revoke_invitation(principal, organization_id, invitation_id)
    return Response(status_code=204)


@router.post("/organization-invitations/accept", response_model=MembershipView)
def accept_invitation(payload: AcceptRequest, principal: Principal, service: Service) -> MembershipView:
    return _mem(service.accept_invitation(principal, payload.invitation_code))


@router.post("/organizations/{organization_id}/capabilities", response_model=CapabilityView, status_code=201)
def request_capability(organization_id: OrgId, payload: CapabilityRequest, principal: Principal,
                       service: Service) -> CapabilityView:
    data = payload.model_dump(by_alias=False)
    kind = data.pop("type")
    return _cap(service.request_capability(principal, organization_id, kind, **data))


@router.get("/organizations/{organization_id}/capabilities", response_model=list[CapabilityView])
def list_capabilities(organization_id: OrgId, principal: Principal, service: Service) -> list[CapabilityView]:
    return [_cap(row) for row in service.capabilities(principal, organization_id)]


# ------------------------------------------------------------------ platform trust review
Reviewer = Annotated[AuthenticatedPrincipal, Depends(require_permission(Permission.TRUST_REVIEW_DECIDE))]


@router.get("/trust-review/organizations", response_model=list[ReviewItem])
def organization_queue(reviewer: Reviewer, service: Service,
                       state: Annotated[Literal["SUBMITTED", "ACTIVE", "REJECTED", "SUSPENDED", "REVOKED"],
                                        Query(alias="status")] = "SUBMITTED") -> list[ReviewItem]:
    return [ReviewItem(organization=_org(row), applicant_user_id=row["application"]["applicantUserId"],
                       applicant_title=row["application"]["applicantTitle"],
                       authority_evidence=row["application"]["authorityEvidence"],
                       official_contact=row["officialContact"], intended_use=row["application"]["intendedUse"])
            for row in service.review_queue(state)]


@router.post("/trust-review/organizations/{organization_id}/decision", response_model=OrganizationView)
def decide_organization(organization_id: OrgId, payload: OrganizationDecision, reviewer: Reviewer,
                        service: Service, step_up: StepUpService = Depends(get_step_up_service),
                        step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
                        ) -> OrganizationView:
    step_up.require(reviewer, step_up_token, action="trust-review.decide", resource=organization_id)
    data = payload.model_dump(by_alias=False)
    decision = data.pop("decision")
    return _org(service.decide_organization(reviewer, organization_id, decision, **data))


@router.get("/trust-review/capabilities", response_model=list[CapabilityView])
def capability_queue(reviewer: Reviewer, service: Service,
                     state: Annotated[Literal["PENDING", "ACTIVE", "REJECTED", "SUSPENDED", "REVOKED"],
                                      Query(alias="status")] = "PENDING") -> list[CapabilityView]:
    return [_cap(row) for row in service.capability_queue(state)]


@router.post("/trust-review/capabilities/{capability_id}/decision", response_model=CapabilityView)
def decide_capability(capability_id: Annotated[str, Path(pattern=_CAP)], payload: CapabilityDecision,
                      reviewer: Reviewer, service: Service, step_up: StepUpService = Depends(get_step_up_service),
                      step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
                      ) -> CapabilityView:
    step_up.require(reviewer, step_up_token, action="trust-review.decide", resource=capability_id)
    return _cap(service.decide_capability(reviewer, capability_id, payload.decision, payload.note))
