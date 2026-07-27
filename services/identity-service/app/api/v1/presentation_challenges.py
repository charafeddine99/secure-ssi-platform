from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from app.api.v1.dependencies import (
    get_presentation_challenge_service,
    require_permission,
)
from app.application.services.holder_wallet_service import (
    PresentationChallengeService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiErrorResponse
from app.schemas.holder_wallet_api import (
    PresentationChallengeCreateRequest,
    PresentationChallengeResponse,
)


router = APIRouter(
    prefix="/presentation-challenges",
    tags=["presentation-challenges"],
)
_CHALLENGE_ID_PATTERN = r"^challenge_[A-Za-z0-9_-]{16,80}$"
_ERRORS = {
    400: {"model": ApiErrorResponse},
    401: {"model": ApiErrorResponse},
    403: {"model": ApiErrorResponse},
    404: {
        "model": ApiErrorResponse,
        "description": "The challenge is absent or hidden from this user.",
    },
    409: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}


@router.post(
    "",
    response_model=PresentationChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a cryptographically random presentation challenge",
    responses=_ERRORS,
)
def issue_challenge(
    payload: PresentationChallengeCreateRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATION_CHALLENGES_CREATE)
    ),
    service: PresentationChallengeService = Depends(
        get_presentation_challenge_service
    ),
) -> PresentationChallengeResponse:
    return PresentationChallengeResponse.from_domain(
        service.issue(
            domain=payload.domain,
            audience=payload.audience,
            requested_holder_did=payload.requestedHolderDid,
            issued_by=principal.id,
            lifetime_seconds=payload.lifetimeSeconds,
            correlation_id=request.state.request_id,
        )
    )


@router.get(
    "/{challenge_id}",
    response_model=PresentationChallengeResponse,
    summary="Read an authorized challenge lifecycle record",
    responses=_ERRORS,
)
def get_challenge(
    challenge_id: Annotated[
        str,
        Path(pattern=_CHALLENGE_ID_PATTERN),
    ],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATION_CHALLENGES_READ)
    ),
    service: PresentationChallengeService = Depends(
        get_presentation_challenge_service
    ),
) -> PresentationChallengeResponse:
    return PresentationChallengeResponse.from_domain(
        service.get_authorized(challenge_id, actor_id=principal.id)
    )
