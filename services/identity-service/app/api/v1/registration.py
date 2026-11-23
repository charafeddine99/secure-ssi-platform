"""Account creation.

Holders register themselves. Issuers and Verifiers apply, and an administrator
decides, because those roles act for an organisation. Administrators join only
by a one-time invitation from another administrator. The public answer is the
same whether or not the address already exists, so it cannot probe accounts.
E-mail ownership is not verified: no mail provider is configured.
"""

import logging
import os
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, status
from pydantic import Field

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_auth_settings,
    get_mongo_connection_manager,
    get_password_hasher,
    get_step_up_service,
    get_user_repository,
    require_permission,
)
from app.application.ports.repositories import AuditEventRepository, UserRepository
from app.application.services.step_up_service import StepUpService
from app.config.environment_policy import is_production_like
from app.domain.auth import AuthenticatedPrincipal
from app.domain.password_policy import MAXIMUM_LENGTH, password_problem
from app.domain.permissions import Permission, Role
from app.domain.persistence import AuditEvent, AuditEventType, DuplicateEntityError, PersistedUser
from app.infrastructure.persistence.mappers import new_object_id
from app.schemas.credential_api import ApiModel

_LOGGER = logging.getLogger(__name__)
router = APIRouter(tags=["registration"])

ONBOARDING_COLLECTION = "onboarding_requests"
INVITATIONS_COLLECTION = "admin_invitations"
INVITATION_LIFETIME = timedelta(hours=24)
_EMAIL = r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$"
_MESSAGES = {
    "holder": "If this address can be registered, you can now sign in.",
    "issuer": "If this address can be registered, your application is waiting for an administrator.",
    "verifier": "If this address can be registered, your application is waiting for an administrator.",
    "admin": "If the invitation is valid, you can now sign in.",
}


class RegisterRequest(ApiModel):
    email: str = Field(pattern=_EMAIL, max_length=254)
    display_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=1, max_length=MAXIMUM_LENGTH)
    role: Literal["holder", "issuer", "verifier", "admin"] = "holder"
    organization: str | None = Field(default=None, min_length=2, max_length=200)
    purpose: str | None = Field(default=None, min_length=3, max_length=500)
    invitation_code: str | None = Field(default=None, min_length=16, max_length=200)


class RegisterResponse(ApiModel):
    status: str = "RECEIVED"
    message: str


class OnboardingItem(ApiModel):
    request_id: str
    email: str
    display_name: str
    role: str
    organization: str
    purpose: str
    status: str
    created_at: datetime
    decided_at: datetime | None = None
    decision_note: str | None = None


class OnboardingDecision(ApiModel):
    note: str = Field(min_length=3, max_length=500)


class InviteRequest(ApiModel):
    email: str = Field(pattern=_EMAIL, max_length=254)


class InviteResponse(ApiModel):
    invitation_code: str
    expires_at: datetime


def _self_registration_enabled(settings: Any) -> bool:
    """Production-like modes need an explicit opt-in, as addresses are unverified."""
    value = os.getenv("IDENTITY_SELF_REGISTRATION_ENABLED", "").strip().casefold()
    if value:
        return value in {"1", "true", "yes"}
    return not is_production_like(settings.environment)


def _digest(code: str) -> str:
    return sha256(code.encode()).hexdigest()


def _audit(events: AuditEventRepository, event_type: AuditEventType, subject: str, actor: str | None) -> None:
    now = datetime.now(UTC)
    try:
        events.append(AuditEvent(
            id=new_object_id(), event_type=event_type, subject_id=subject, actor_id=actor,
            correlation_id=None, metadata={}, created_at=now, updated_at=now, version=1,
        ))
    except Exception as error:
        _LOGGER.warning("Account audit event was not written (%s)", type(error).__name__)


def _item(row: dict[str, Any]) -> OnboardingItem:
    return OnboardingItem(
        request_id=row["_id"], email=row["email"], display_name=row["displayName"], role=row["role"],
        organization=row["organization"], purpose=row["purpose"], status=row["status"],
        created_at=row["createdAt"], decided_at=row.get("decidedAt"), decision_note=row.get("decisionNote"),
    )


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_202_ACCEPTED)
def register_account(
    payload: RegisterRequest,
    settings: Any = Depends(get_auth_settings),
    users: UserRepository = Depends(get_user_repository),
    hasher: Any = Depends(get_password_hasher),
    manager: Any = Depends(get_mongo_connection_manager),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
) -> RegisterResponse:
    if settings.user_provider != "mongodb":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Registration needs the persistent account store.")
    if payload.role != "admin" and not _self_registration_enabled(settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Registration is closed.")
    email = payload.email.strip().casefold()
    problem = password_problem(payload.password, username=email)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=problem)
    if payload.role in ("issuer", "verifier") and not (payload.organization and payload.purpose):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Give your organisation and why you need this role.")
    # Always hash, so a known address does not answer faster.
    password_hash = hasher.hash_password(payload.password)
    database = manager.database
    if payload.role == "admin":
        now = datetime.now(UTC)
        claimed = database[INVITATIONS_COLLECTION].update_one(
            {"_id": _digest(payload.invitation_code or ""), "email": email, "usedAt": None, "expiresAt": {"$gte": now}},
            {"$set": {"usedAt": now}},
        )
        if not claimed.matched_count:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This invitation is not valid.")
    response = RegisterResponse(message=_MESSAGES[payload.role])
    if users.get_by_username(email) is not None:
        return response
    enabled = payload.role in ("holder", "admin")
    user = PersistedUser(
        id=new_object_id(), username=email, display_name=payload.display_name.strip(),
        roles=(Role(payload.role),), enabled=enabled, password_hash=password_hash,
    )
    try:
        users.add(user)
    except DuplicateEntityError:
        return response
    if not enabled:
        database[ONBOARDING_COLLECTION].insert_one({
            "_id": f"onb_{secrets.token_urlsafe(16)}", "userId": user.id, "email": email,
            "displayName": user.display_name, "role": payload.role, "organization": payload.organization,
            "purpose": payload.purpose, "status": "PENDING", "createdAt": datetime.now(UTC),
        })
    _audit(audit_events, AuditEventType.ACCOUNT_REGISTERED if enabled else AuditEventType.ONBOARDING_REQUESTED, user.id, user.id)
    return response


@router.get("/admin/onboarding", response_model=list[OnboardingItem])
def list_onboarding(
    state: Annotated[Literal["PENDING", "APPROVED", "REJECTED"], Query(alias="status")] = "PENDING",
    _principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_USERS_READ)),
    manager: Any = Depends(get_mongo_connection_manager),
) -> list[OnboardingItem]:
    rows = manager.database[ONBOARDING_COLLECTION].find({"status": state}).sort("createdAt", -1).limit(200)
    return [_item(row) for row in rows]


def _decide(
    request_id: str,
    decision: str,
    note: str,
    principal: AuthenticatedPrincipal,
    manager: Any,
) -> dict[str, Any]:
    collection = manager.database[ONBOARDING_COLLECTION]
    result = collection.update_one(
        {"_id": request_id, "status": "PENDING"},
        {"$set": {"status": decision, "decidedAt": datetime.now(UTC), "decidedBy": principal.id, "decisionNote": note}},
    )
    if not result.matched_count:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This request is not pending.")
    return collection.find_one({"_id": request_id})


@router.post("/admin/onboarding/{request_id}/approve", response_model=OnboardingItem)
def approve_onboarding(
    request_id: Annotated[str, Path(max_length=64)],
    payload: OnboardingDecision,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_USERS_WRITE)),
    manager: Any = Depends(get_mongo_connection_manager),
    users: UserRepository = Depends(get_user_repository),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
    step_up: StepUpService = Depends(get_step_up_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
) -> OnboardingItem:
    step_up.require(principal, step_up_token, action="onboarding.decide", resource=request_id)
    row = _decide(request_id, "APPROVED", payload.note, principal, manager)
    account = users.get_by_id(row["userId"])
    if account is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="The account no longer exists.")
    users.update(replace(account, enabled=True), expected_version=account.version)
    _audit(audit_events, AuditEventType.ONBOARDING_APPROVED, account.id, principal.id)
    return _item(row)


@router.post("/admin/onboarding/{request_id}/reject", response_model=OnboardingItem)
def reject_onboarding(
    request_id: Annotated[str, Path(max_length=64)],
    payload: OnboardingDecision,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_USERS_WRITE)),
    manager: Any = Depends(get_mongo_connection_manager),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
    step_up: StepUpService = Depends(get_step_up_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
) -> OnboardingItem:
    step_up.require(principal, step_up_token, action="onboarding.decide", resource=request_id)
    row = _decide(request_id, "REJECTED", payload.note, principal, manager)
    _audit(audit_events, AuditEventType.ONBOARDING_REJECTED, row["userId"], principal.id)
    return _item(row)


@router.post("/admin/invitations", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite_administrator(
    payload: InviteRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.ADMIN_USERS_WRITE)),
    manager: Any = Depends(get_mongo_connection_manager),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
    step_up: StepUpService = Depends(get_step_up_service),
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
) -> InviteResponse:
    """The code is shown once. Only its digest is stored."""
    email = payload.email.strip().casefold()
    step_up.require(principal, step_up_token, action="admin.invite", resource=email)
    code = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + INVITATION_LIFETIME
    manager.database[INVITATIONS_COLLECTION].insert_one({
        "_id": _digest(code), "email": email, "invitedBy": principal.id,
        "expiresAt": expires, "usedAt": None, "createdAt": datetime.now(UTC),
    })
    _audit(audit_events, AuditEventType.ADMIN_INVITED, _digest(email), principal.id)
    return InviteResponse(invitation_code=code, expires_at=expires)
