"""Password change, security keys and credential re-issuance."""

from dataclasses import replace
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, Response
from pydantic import Field

from app.api.v1.dependencies import (
    get_authentication_service,
    get_current_principal,
    get_oid4vci_service,
    get_password_hasher,
    get_reissuance_service,
    get_step_up_service,
    get_user_repository,
    get_webauthn_service,
    require_permission,
)
from app.api.v1.issuer_scope import require_issuer_did
from app.application.services.authentication_service import (
    AuthenticationService,
)
from app.application.services.oid4vci_service import Oid4vciService
from app.application.services.reissuance_service import (
    ReissuanceError,
    ReissuanceNotFoundError,
    ReissuanceRequest,
    ReissuanceService,
)
from app.application.services.step_up_service import (
    StepUpRequiredError,
    StepUpService,
)
from app.application.services.webauthn_service import WebAuthnService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import InvalidCredentialsError
from app.domain.password_policy import password_problem
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiModel


router = APIRouter(tags=["account-lifecycle"])
_WALLET = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_REQUEST = r"^reissue_[A-Za-z0-9_-]{16,64}$"
MINIMUM_PASSWORD_LENGTH = 15


class PasswordChangeRequest(ApiModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=MINIMUM_PASSWORD_LENGTH, max_length=1024)


class SecurityKeyOptionsRequest(ApiModel):
    password: str = Field(min_length=1, max_length=1024)


class SecurityKeyVerifyRequest(ApiModel):
    credential: dict[str, Any]


class StepUpTarget(ApiModel):
    action: str = Field(min_length=3, max_length=64)
    resource: str = Field(min_length=1, max_length=256)


class SecurityKeyStepUpRequest(StepUpTarget):
    credential: dict[str, Any]


class StepUpTokenResponse(ApiModel):
    step_up_token: str
    expires_in: int


class SecurityKeyStatusResponse(ApiModel):
    configured: bool
    enrolled: bool


class ReissuanceCreateRequest(ApiModel):
    credential_id: str = Field(min_length=3, max_length=2048)


class ReissuanceResponse(ApiModel):
    request_id: str
    credential_id: str
    credential_type: str
    issuer_did: str
    old_holder_did: str
    new_holder_did: str
    status: str
    created_at: datetime
    decided_at: datetime | None
    offer_link: str | None

    @classmethod
    def from_domain(
        cls,
        value: ReissuanceRequest,
        *,
        show_offer: bool = False,
    ) -> "ReissuanceResponse":
        return cls(
            request_id=value.request_id,
            credential_id=value.credential_id,
            credential_type=value.credential_type,
            issuer_did=value.issuer_did,
            old_holder_did=value.old_holder_did,
            new_holder_did=value.new_holder_did,
            status=value.status,
            created_at=value.created_at,
            decided_at=value.decided_at,
            offer_link=value.offer_link if show_offer else None,
        )


class ReissuanceListResponse(ApiModel):
    items: list[ReissuanceResponse]


@router.post("/auth/password", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    step_up_token: Annotated[str | None, Header(alias="X-Step-Up-Token")] = None,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    authentication: AuthenticationService = Depends(get_authentication_service),
    step_up: StepUpService = Depends(get_step_up_service),
    users: Any = Depends(get_user_repository),
    hasher: Any = Depends(get_password_hasher),
) -> Response:
    step_up.require(
        principal,
        step_up_token,
        action="account.password.change",
        resource=principal.id,
    )
    try:
        authentication.authenticate(
            username=principal.username,
            password=payload.current_password,
        )
    except InvalidCredentialsError as error:
        raise StepUpRequiredError("The current password is not correct.") from error
    user = users.get_by_username(principal.username)
    if user is None:
        raise StepUpRequiredError("This account cannot change its password here.")
    problem = password_problem(payload.new_password, username=principal.username)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    users.update(
        replace(user, password_hash=hasher.hash_password(payload.new_password)),
        expected_version=user.version,
    )
    # Anyone else holding a session loses it. So does this one: sign in again.
    authentication.revoke_subject(principal.id, reason="password_changed")
    return Response(status_code=204)


@router.get("/auth/webauthn", response_model=SecurityKeyStatusResponse)
def security_key_status(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: WebAuthnService = Depends(get_webauthn_service),
) -> SecurityKeyStatusResponse:
    return SecurityKeyStatusResponse(
        configured=service.configured,
        enrolled=service.configured and service.enrolled(principal.id),
    )


@router.post("/auth/webauthn/register/options")
def security_key_registration_options(
    payload: SecurityKeyOptionsRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    authentication: AuthenticationService = Depends(get_authentication_service),
    service: WebAuthnService = Depends(get_webauthn_service),
) -> dict[str, Any]:
    # A stolen session alone must not be able to add its own authenticator.
    try:
        authentication.authenticate(
            username=principal.username,
            password=payload.password,
        )
    except InvalidCredentialsError as error:
        raise StepUpRequiredError("The password is not correct.") from error
    return service.registration_options(principal)


@router.post("/auth/webauthn/register/verify", response_model=SecurityKeyStatusResponse)
def security_key_registration_verify(
    payload: SecurityKeyVerifyRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: WebAuthnService = Depends(get_webauthn_service),
) -> SecurityKeyStatusResponse:
    service.verify_registration(principal, payload.credential)
    return SecurityKeyStatusResponse(configured=True, enrolled=True)


@router.post("/auth/webauthn/step-up/options")
def security_key_step_up_options(
    payload: StepUpTarget,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: WebAuthnService = Depends(get_webauthn_service),
) -> dict[str, Any]:
    return service.authentication_options(
        principal,
        action=payload.action,
        resource=payload.resource,
    )


@router.post("/auth/webauthn/step-up/verify", response_model=StepUpTokenResponse)
def security_key_step_up_verify(
    payload: SecurityKeyStepUpRequest,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: WebAuthnService = Depends(get_webauthn_service),
) -> StepUpTokenResponse:
    token, lifetime = service.verify_step_up(
        principal,
        payload.credential,
        action=payload.action,
        resource=payload.resource,
    )
    response.headers["Cache-Control"] = "no-store"
    return StepUpTokenResponse(step_up_token=token, expires_in=lifetime)


def _translate(operation):
    try:
        return operation()
    except ReissuanceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ReissuanceError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/wallets/{wallet_id}/reissuance-requests",
    response_model=ReissuanceResponse,
    status_code=201,
)
def request_reissuance(
    wallet_id: Annotated[str, Path(pattern=_WALLET)],
    payload: ReissuanceCreateRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    service: ReissuanceService = Depends(get_reissuance_service),
) -> ReissuanceResponse:
    return ReissuanceResponse.from_domain(
        _translate(
            lambda: service.request(
                wallet_id,
                payload.credential_id,
                owner_user_id=principal.id,
            )
        )
    )


@router.get("/reissuance-requests/mine", response_model=ReissuanceListResponse)
def my_reissuance_requests(
    response: Response,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    service: ReissuanceService = Depends(get_reissuance_service),
) -> ReissuanceListResponse:
    response.headers["Cache-Control"] = "no-store"
    return ReissuanceListResponse(
        items=[
            ReissuanceResponse.from_domain(item, show_offer=True)
            for item in service.list_for_holder(principal.id)
        ]
    )


@router.get("/reissuance-requests/issuer", response_model=ReissuanceListResponse)
def issuer_reissuance_requests(
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_SIGN)
    ),
    service: ReissuanceService = Depends(get_reissuance_service),
) -> ReissuanceListResponse:
    return ReissuanceListResponse(
        items=[
            ReissuanceResponse.from_domain(item)
            for item in service.list_for_issuer(require_issuer_did(principal))
        ]
    )


@router.post(
    "/reissuance-requests/{request_id}/approve",
    response_model=ReissuanceResponse,
)
def approve_reissuance(
    request_id: Annotated[str, Path(pattern=_REQUEST)],
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_SIGN)
    ),
    service: ReissuanceService = Depends(get_reissuance_service),
    offers: Oid4vciService = Depends(get_oid4vci_service),
) -> ReissuanceResponse:
    issuer_did = require_issuer_did(principal)
    base_url = str(request.base_url).rstrip("/")

    def create_offer(credential_type: str, claims: dict[str, Any]) -> str:
        offer = offers.create_offer(
            issuer_did=issuer_did,
            credential_configuration_ids=(credential_type,),
            subject_data=claims,
            ttl_seconds=1800,
        )
        return offer.to_deep_link_uri(base_url)

    return ReissuanceResponse.from_domain(
        _translate(
            lambda: service.approve(
                request_id,
                issuer_did=issuer_did,
                create_offer=create_offer,
            )
        )
    )


@router.post(
    "/reissuance-requests/{request_id}/reject",
    response_model=ReissuanceResponse,
)
def reject_reissuance(
    request_id: Annotated[str, Path(pattern=_REQUEST)],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_SIGN)
    ),
    service: ReissuanceService = Depends(get_reissuance_service),
) -> ReissuanceResponse:
    return ReissuanceResponse.from_domain(
        _translate(
            lambda: service.reject(
                request_id,
                issuer_did=require_issuer_did(principal),
            )
        )
    )
