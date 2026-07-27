from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from app.api.v1.dependencies import (
    get_holder_presentation_service,
    get_presentation_reconciliation_service,
    get_verifier_presentation_service,
    require_permission,
)
from app.application.services.presentation_service import (
    HolderPresentationService,
    PresentationReconciliationService,
    VerifierPresentationService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.permissions import Role
from app.domain.exceptions import PermissionDeniedError
from app.schemas.credential_api import ApiErrorResponse
from app.schemas.presentation_api import (
    PresentationCreateRequest,
    PresentationResponse,
    PresentationVerificationResponse,
    PresentationVerifyRequest,
)


router = APIRouter(prefix="/presentations", tags=["presentations"])
_PRESENTATION_ID = (
    r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "Presentation input violates the local VP profile.",
    },
    401: {
        "model": ApiErrorResponse,
        "description": "Bearer authentication is missing or invalid.",
    },
    403: {
        "model": ApiErrorResponse,
        "description": "The current user cannot perform this VP operation.",
    },
    404: {
        "model": ApiErrorResponse,
        "description": "The presentation or a credential does not exist.",
    },
    409: {
        "model": ApiErrorResponse,
        "description": "The challenge or verification nonce was already used.",
    },
    413: {
        "model": ApiErrorResponse,
        "description": "The presentation exceeds the request size limit.",
    },
    422: {
        "model": ApiErrorResponse,
        "description": "The request envelope is invalid.",
    },
    500: {
        "model": ApiErrorResponse,
        "description": "The presentation operation failed safely.",
    },
    503: {
        "model": ApiErrorResponse,
        "description": "MongoDB persistence is unavailable.",
    },
}


@router.post(
    "/create",
    response_model=PresentationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and sign a Verifiable Presentation",
    description=(
        "Builds a short-lived W3C VC Data Model 2.0 presentation from one "
        "or more previously issued active credentials and binds its holder "
        "proof to a single-use challenge and verifier domain."
    ),
    responses=_ERROR_RESPONSES,
)
def create_presentation(
    payload: PresentationCreateRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_CREATE)
    ),
    service: HolderPresentationService = Depends(
        get_holder_presentation_service
    ),
) -> PresentationResponse:
    presentation = service.create(
        payload.credentialIds,
        challenge=payload.challenge,
        domain=payload.domain,
        lifetime_seconds=payload.lifetimeSeconds,
        actor_id=principal.id,
        correlation_id=request.state.request_id,
        wallet_id=payload.walletId,
        challenge_id=payload.challengeId,
        audience=payload.audience,
    )
    return PresentationResponse.from_domain(presentation)


@router.post(
    "/verify",
    response_model=PresentationVerificationResponse,
    summary="Verify and consume a Verifiable Presentation",
    description=(
        "Atomically consumes the persisted presentation nonce, verifies the "
        "holder proof, expected challenge/domain, lifetime, holder binding, "
        "credential proofs, persistence hashes, and current revocation state."
    ),
    responses=_ERROR_RESPONSES,
)
def verify_presentation(
    payload: PresentationVerifyRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_VERIFY)
    ),
    service: VerifierPresentationService = Depends(
        get_verifier_presentation_service
    ),
) -> PresentationVerificationResponse:
    result = service.verify(
        payload.presentation,
        expected_challenge=payload.expectedChallenge,
        expected_domain=payload.expectedDomain,
        actor_id=principal.id,
        correlation_id=request.state.request_id,
        expected_audience=payload.expectedAudience,
    )
    return PresentationVerificationResponse.from_domain(result)


@router.get(
    "/{presentation_id}",
    response_model=PresentationResponse,
    summary="Read a persisted Verifiable Presentation",
    description=(
        "Returns the exact persisted presentation and its bounded lifecycle "
        "metadata to authorized local holders, verifiers, issuers, or admins."
    ),
    responses=_ERROR_RESPONSES,
)
def get_presentation(
    presentation_id: Annotated[
        str,
        Path(pattern=_PRESENTATION_ID),
    ],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_READ)
    ),
    service: HolderPresentationService = Depends(
        get_holder_presentation_service
    ),
) -> PresentationResponse:
    return PresentationResponse.from_domain(
        service.get(presentation_id, actor_id=principal.id)
    )


@router.post(
    "/{presentation_id}/reconcile",
    response_model=PresentationResponse,
    summary="Reconcile a stale PROCESSING presentation",
    description=(
        "Allows an administrator to idempotently recover a presentation "
        "whose verification process stopped after the atomic claim."
    ),
    responses=_ERROR_RESPONSES,
)
def reconcile_presentation(
    presentation_id: Annotated[
        str,
        Path(pattern=_PRESENTATION_ID),
    ],
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_RECONCILE)
    ),
    service: PresentationReconciliationService = Depends(
        get_presentation_reconciliation_service
    ),
) -> PresentationResponse:
    if Role.ADMIN not in principal.roles:
        raise PermissionDeniedError(
            "Presentation reconciliation requires the admin role."
        )
    return PresentationResponse.from_domain(
        service.reconcile(
            presentation_id,
            actor_id=principal.id,
            correlation_id=request.state.request_id,
        )
    )
