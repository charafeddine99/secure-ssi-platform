import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.domain.exceptions import (
    AccessTokenExpiredError,
    AccessTokenInvalidAudienceError,
    AccessTokenInvalidIssuerError,
    AccessTokenInvalidUseError,
    AccessTokenNotActiveError,
    AuthConfigurationError,
    AuthenticationError,
    AuthenticationRequiredError,
    CanonicalizationError,
    CredentialProofError,
    ExistingProofError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    PermissionDeniedError,
    UnknownIssuerError,
    UserDisabledError,
    UserNotFoundError,
)
from app.domain.credential_status import (
    CredentialAlreadyRevokedError,
    CredentialNotFoundError,
    CredentialStatusError,
    InvalidCredentialStatusTransitionError,
    InvalidRevocationReasonError,
)
from app.domain.issuance import (
    CredentialAlreadyIssuedError,
    CredentialIssuanceError,
    IssuanceStatusSlotConflictError,
    IssuanceValidationError,
)
from app.domain.bitstring_status_list import (
    StatusListCapacityError,
    StatusListConflictError,
    StatusListError,
    StatusListGenerationError,
    StatusListNotFoundError,
    StatusListVersionNotFoundError,
)
from app.domain.persistence import (
    DocumentMappingError,
    DuplicateEntityError,
    EntityNotFoundError,
    OptimisticLockError,
    PersistenceConfigurationError,
    PersistenceUnavailableError,
    RepositoryError,
)
from app.domain.presentation import (
    InvalidPresentationError,
    PresentationCredentialError,
    PresentationError,
    PresentationNotFoundError,
    PresentationReplayError,
)
from app.domain.holder_wallet import (
    HolderOwnershipError,
    HolderWalletConflictError,
    HolderWalletError,
    HolderWalletNotFoundError,
    HolderWalletUnavailableError,
)
from app.domain.presentation_challenge import (
    PresentationChallengeConflictError,
    PresentationChallengeError,
    PresentationChallengeExpiredError,
    PresentationChallengeNotFoundError,
    PresentationChallengeRejectedError,
    PresentationChallengeReplayError,
)
from app.domain.vc import CredentialValidationError, VerificationReasonCode
from app.schemas.credential_api import (
    ApiError,
    ApiErrorDetail,
    ApiErrorResponse,
)


LOGGER = logging.getLogger("identity_service.api")


def build_error_response(
    *,
    request_id: str,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str | None]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    model = ApiErrorResponse(
        error=ApiError(
            code=code,
            message=message,
            details=[
                ApiErrorDetail.model_validate(detail)
                for detail in (details or [])
            ],
        ),
        request_id=request_id,
    )
    response_headers = {"X-Request-ID": request_id}
    response_headers.update(headers or {})
    return JSONResponse(
        status_code=status_code,
        content=model.model_dump(mode="json", by_alias=True),
        headers=response_headers,
    )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unavailable")


async def request_validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    details = [
        {
            "code": str(item.get("type", "invalid_value")),
            "location": ".".join(str(part) for part in item.get("loc", ())),
        }
        for item in error.errors()
    ]
    return build_error_response(
        request_id=_request_id(request),
        status_code=422,
        code="REQUEST_VALIDATION_FAILED",
        message="The request envelope is invalid.",
        details=details,
    )


async def credential_validation_error_handler(
    request: Request,
    error: CredentialValidationError,
) -> JSONResponse:
    if error.code is VerificationReasonCode.CREDENTIAL_TOO_LARGE:
        return build_error_response(
            request_id=_request_id(request),
            status_code=413,
            code=error.code.value,
            message="The credential exceeds the configured size limit.",
        )
    return build_error_response(
        request_id=_request_id(request),
        status_code=400,
        code=error.code.value,
        message="The credential does not satisfy the local profile.",
    )


async def authentication_error_handler(
    request: Request,
    error: AuthenticationError,
) -> JSONResponse:
    status_code = 401
    code = "INVALID_ACCESS_TOKEN"
    message = "The access token is invalid."
    headers = {
        "WWW-Authenticate": "Bearer",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    }

    if isinstance(error, AuthConfigurationError):
        status_code = 500
        code = "AUTH_CONFIGURATION_ERROR"
        message = "Authentication is not safely configured."
        headers.pop("WWW-Authenticate")
    elif isinstance(error, PermissionDeniedError):
        status_code = 403
        code = "PERMISSION_DENIED"
        message = "The authenticated user lacks the required permission."
        headers.pop("WWW-Authenticate")
    elif isinstance(error, AuthenticationRequiredError):
        code = "AUTHENTICATION_REQUIRED"
        message = "Bearer authentication is required."
    elif isinstance(error, InvalidCredentialsError):
        code = "INVALID_CREDENTIALS"
        message = "Invalid username or password."
    elif isinstance(error, AccessTokenExpiredError):
        code = "ACCESS_TOKEN_EXPIRED"
        message = "The access token has expired."
    elif isinstance(error, AccessTokenNotActiveError):
        code = "ACCESS_TOKEN_NOT_ACTIVE"
        message = "The access token is not active."
    elif isinstance(error, AccessTokenInvalidIssuerError):
        code = "ACCESS_TOKEN_INVALID_ISSUER"
        message = "The access token issuer is invalid."
    elif isinstance(error, AccessTokenInvalidAudienceError):
        code = "ACCESS_TOKEN_INVALID_AUDIENCE"
        message = "The access token audience is invalid."
    elif isinstance(error, AccessTokenInvalidUseError):
        code = "ACCESS_TOKEN_INVALID_USE"
        message = "The token cannot be used as an access token."
    elif isinstance(error, UserNotFoundError):
        code = "USER_NOT_FOUND"
        message = "The access token subject is unavailable."
    elif isinstance(error, UserDisabledError):
        code = "USER_DISABLED"
        message = "The access token subject is disabled."
    elif isinstance(error, InvalidAccessTokenError):
        code = "INVALID_ACCESS_TOKEN"

    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
        headers=headers,
    )


async def credential_proof_error_handler(
    request: Request,
    error: CredentialProofError,
) -> JSONResponse:
    if isinstance(error, ExistingProofError):
        return build_error_response(
            request_id=_request_id(request),
            status_code=409,
            code="CREDENTIAL_ALREADY_SIGNED",
            message="Credential already contains a proof.",
        )
    if isinstance(error, UnknownIssuerError):
        return build_error_response(
            request_id=_request_id(request),
            status_code=400,
            code="UNKNOWN_ISSUER",
            message="The issuer is not supported by this local prototype.",
        )
    if isinstance(error, CanonicalizationError):
        return build_error_response(
            request_id=_request_id(request),
            status_code=400,
            code="CREDENTIAL_NOT_CANONICALIZABLE",
            message="The credential cannot be processed by the local profile.",
        )
    LOGGER.error(
        "Credential operation failed safely request_id=%s",
        _request_id(request),
    )
    return build_error_response(
        request_id=_request_id(request),
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="The credential operation could not be completed.",
    )


async def repository_error_handler(
    request: Request,
    error: RepositoryError,
) -> JSONResponse:
    status_code = 500
    code = "PERSISTENCE_ERROR"
    message = "The persistence operation could not be completed."
    if isinstance(error, DuplicateEntityError):
        status_code = 409
        code = "PERSISTENCE_DUPLICATE"
        message = "A record with the same unique identifier already exists."
    elif isinstance(error, OptimisticLockError):
        status_code = 409
        code = "PERSISTENCE_VERSION_CONFLICT"
        message = "The record was changed by another operation."
    elif isinstance(error, EntityNotFoundError):
        status_code = 404
        code = "PERSISTENCE_RECORD_NOT_FOUND"
        message = "The requested active record was not found."
    elif isinstance(error, PersistenceUnavailableError):
        status_code = 503
        code = "PERSISTENCE_UNAVAILABLE"
        message = "The persistence service is temporarily unavailable."
    elif isinstance(
        error,
        (PersistenceConfigurationError, DocumentMappingError),
    ):
        LOGGER.error(
            "Persistence configuration or mapping failure request_id=%s",
            _request_id(request),
        )
    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
    )


async def credential_status_error_handler(
    request: Request,
    error: CredentialStatusError,
) -> JSONResponse:
    status_code = 409
    code = "INVALID_CREDENTIAL_STATUS_TRANSITION"
    message = "The credential status transition is not allowed."
    if isinstance(error, CredentialNotFoundError):
        status_code = 404
        code = "CREDENTIAL_NOT_FOUND"
        message = "The requested credential was not found."
    elif isinstance(error, CredentialAlreadyRevokedError):
        code = "CREDENTIAL_ALREADY_REVOKED"
        message = "The credential has already been revoked."
    elif isinstance(error, InvalidRevocationReasonError):
        status_code = 400
        code = "INVALID_REVOCATION_REASON"
        message = "The revocation reason is invalid."
    elif isinstance(error, InvalidCredentialStatusTransitionError):
        code = "INVALID_CREDENTIAL_STATUS_TRANSITION"
    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
    )


async def credential_issuance_error_handler(
    request: Request,
    error: CredentialIssuanceError,
) -> JSONResponse:
    status_code = 409
    code = "CREDENTIAL_ISSUANCE_CONFLICT"
    message = "The credential could not be issued atomically."
    if isinstance(error, CredentialAlreadyIssuedError):
        code = "CREDENTIAL_ALREADY_ISSUED"
        message = "The credential id has already been issued."
    elif isinstance(error, IssuanceValidationError):
        status_code = 400
        code = "INVALID_ISSUANCE_INPUT"
        message = "The credential cannot enter the issuance lifecycle."
    elif isinstance(error, IssuanceStatusSlotConflictError):
        code = "STATUS_LIST_SLOT_CONFLICT"
        message = "The status-list slot changed during issuance."
    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
    )


async def status_list_error_handler(
    request: Request,
    error: StatusListError,
) -> JSONResponse:
    status_code = 500
    code = "STATUS_LIST_GENERATION_FAILED"
    message = "The status list could not be generated safely."
    if isinstance(error, StatusListVersionNotFoundError):
        status_code = 404
        code = "STATUS_LIST_VERSION_NOT_FOUND"
        message = "The requested status-list version was not found."
    elif isinstance(error, StatusListNotFoundError):
        status_code = 404
        code = "STATUS_LIST_NOT_FOUND"
        message = "The requested status list was not found."
    elif isinstance(error, StatusListConflictError):
        status_code = 409
        code = "STATUS_LIST_VERSION_CONFLICT"
        message = "The status list changed during publication."
    elif isinstance(error, StatusListCapacityError):
        status_code = 503
        code = "STATUS_LIST_CAPACITY_EXHAUSTED"
        message = "The status list has no available credential entries."
    elif isinstance(error, StatusListGenerationError):
        LOGGER.error(
            "Status list generation failed request_id=%s",
            _request_id(request),
        )
    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
    )


async def presentation_error_handler(
    request: Request,
    error: PresentationError,
) -> JSONResponse:
    status_code = 400
    code = "INVALID_PRESENTATION"
    message = "The presentation does not satisfy the local VP profile."
    if isinstance(error, PresentationNotFoundError):
        status_code = 404
        code = "PRESENTATION_NOT_FOUND"
        message = "The requested presentation was not found."
    elif isinstance(error, PresentationReplayError):
        status_code = 409
        code = "PRESENTATION_REPLAY_DETECTED"
        message = "The challenge or presentation nonce was already consumed."
    elif isinstance(error, PresentationCredentialError):
        code = "PRESENTATION_CREDENTIAL_REJECTED"
        message = "A referenced credential cannot be presented."
    elif isinstance(error, InvalidPresentationError):
        code = "INVALID_PRESENTATION"
    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
    )


async def holder_wallet_error_handler(
    request: Request,
    error: HolderWalletError,
) -> JSONResponse:
    status_code = 409
    code = "HOLDER_WALLET_UNAVAILABLE"
    message = "The holder wallet cannot perform this operation."
    if isinstance(
        error,
        (HolderWalletNotFoundError, HolderOwnershipError),
    ):
        status_code = 404
        code = "HOLDER_WALLET_NOT_FOUND"
        message = "The requested holder wallet was not found."
    elif isinstance(error, HolderWalletConflictError):
        code = "HOLDER_WALLET_CONFLICT"
        message = "The holder wallet conflicts with existing state."
    elif isinstance(error, HolderWalletUnavailableError):
        code = "HOLDER_WALLET_UNAVAILABLE"
    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
    )


async def presentation_challenge_error_handler(
    request: Request,
    error: PresentationChallengeError,
) -> JSONResponse:
    status_code = 409
    code = "PRESENTATION_CHALLENGE_REJECTED"
    message = "The presentation challenge cannot be used."
    if isinstance(error, PresentationChallengeNotFoundError):
        status_code = 404
        code = "PRESENTATION_CHALLENGE_NOT_FOUND"
        message = "The requested presentation challenge was not found."
    elif isinstance(error, PresentationChallengeConflictError):
        code = "PRESENTATION_CHALLENGE_CONFLICT"
        message = "The presentation challenge conflicts with existing state."
    elif isinstance(error, PresentationChallengeReplayError):
        code = "PRESENTATION_CHALLENGE_REPLAY"
        message = "The presentation challenge was already consumed."
    elif isinstance(error, PresentationChallengeExpiredError):
        code = "PRESENTATION_CHALLENGE_EXPIRED"
        message = "The presentation challenge has expired."
    elif isinstance(error, PresentationChallengeRejectedError):
        code = "PRESENTATION_CHALLENGE_REJECTED"
    return build_error_response(
        request_id=_request_id(request),
        status_code=status_code,
        code=code,
        message=message,
    )


async def http_error_handler(
    request: Request,
    error: HTTPException,
) -> JSONResponse:
    return build_error_response(
        request_id=_request_id(request),
        status_code=error.status_code,
        code=f"HTTP_{error.status_code}",
        message="The requested operation could not be completed.",
    )


async def unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    LOGGER.error(
        "Unhandled request failure request_id=%s",
        _request_id(request),
    )
    return build_error_response(
        request_id=_request_id(request),
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred.",
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )
    app.add_exception_handler(
        AuthenticationError,
        authentication_error_handler,
    )
    app.add_exception_handler(
        CredentialValidationError,
        credential_validation_error_handler,
    )
    app.add_exception_handler(
        CredentialProofError,
        credential_proof_error_handler,
    )
    app.add_exception_handler(
        CredentialStatusError,
        credential_status_error_handler,
    )
    app.add_exception_handler(
        CredentialIssuanceError,
        credential_issuance_error_handler,
    )
    app.add_exception_handler(StatusListError, status_list_error_handler)
    app.add_exception_handler(PresentationError, presentation_error_handler)
    app.add_exception_handler(
        HolderWalletError,
        holder_wallet_error_handler,
    )
    app.add_exception_handler(
        PresentationChallengeError,
        presentation_challenge_error_handler,
    )
    app.add_exception_handler(RepositoryError, repository_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
