from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from app.api.v1.dependencies import (
    get_credential_api_service,
    get_credential_issuance_api_service,
    get_credential_revocation_service,
    require_permission,
)
from app.application.services.credential_api_service import CredentialApiService
from app.application.services.credential_revocation_service import (
    CredentialRevocationService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.schemas.credential_api import (
    ApiErrorResponse,
    CredentialCapabilitiesResponse,
    CredentialEnvelope,
    CredentialOperationsResponse,
    CredentialRevocationRequest,
    CredentialSignResponse,
    CredentialStatusResponse,
    CredentialValidationResponse,
    CredentialVerificationResponse,
    DidMethodsResponse,
)


router = APIRouter(prefix="/credentials", tags=["credentials"])
ERROR_RESPONSES = {
    400: {
        "model": ApiErrorResponse,
        "description": "Malformed or unusable credential input.",
    },
    413: {
        "model": ApiErrorResponse,
        "description": "Request or credential size limit exceeded.",
    },
    422: {
        "model": ApiErrorResponse,
        "description": "Request envelope validation failed.",
    },
    500: {
        "model": ApiErrorResponse,
        "description": "Safe internal failure without implementation details.",
    },
}


@router.post(
    "/validate",
    response_model=CredentialValidationResponse,
    summary="Validate a credential profile",
    description=(
        "Checks the local academic VC profile without verifying a signature. "
        "No authentication or persistence is provided."
    ),
    responses=ERROR_RESPONSES,
)
def validate_credential(
    envelope: CredentialEnvelope,
    service: CredentialApiService = Depends(get_credential_api_service),
) -> CredentialValidationResponse:
    result = service.validate_credential(envelope.credential)
    return CredentialValidationResponse.from_domain(result)


@router.post(
    "/sign",
    response_model=CredentialSignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sign a local prototype credential",
    description=(
        "Assigns exactly one Bitstring Status List entry, signs the resulting "
        "credential, and atomically persists both as one MongoDB document. A "
        "local Bearer token with credentials:sign is required."
    ),
    responses={
        **ERROR_RESPONSES,
        401: {
            "model": ApiErrorResponse,
            "description": "Bearer authentication is missing or invalid.",
        },
        403: {
            "model": ApiErrorResponse,
            "description": "The current user cannot sign credentials.",
        },
        409: {
            "model": ApiErrorResponse,
            "description": (
                "The credential is already signed or its id was issued."
            ),
        },
    },
)
def sign_credential(
    envelope: CredentialEnvelope,
    _principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_SIGN)
    ),
    service: CredentialApiService = Depends(
        get_credential_issuance_api_service
    ),
) -> CredentialSignResponse:
    credential = service.sign_credential(envelope.credential)
    return CredentialSignResponse(credential=credential)


@router.post(
    "/verify",
    response_model=CredentialVerificationResponse,
    summary="Verify a signed local credential",
    description=(
        "Runs local profile and Ed25519 proof verification using fixture-only "
        "DID resolution. Invalid proofs normally return HTTP 200 with "
        "valid=false."
    ),
    responses=ERROR_RESPONSES,
)
def verify_credential(
    envelope: CredentialEnvelope,
    service: CredentialApiService = Depends(get_credential_api_service),
) -> CredentialVerificationResponse:
    result = service.verify_credential(envelope.credential)
    return CredentialVerificationResponse.from_domain(result)


@router.post(
    "/{credential_id}/revoke",
    response_model=CredentialStatusResponse,
    summary="Permanently revoke a stored credential",
    description=(
        "Transitions one active, suspended, or expired MongoDB credential to "
        "REVOKED exactly once. A local Bearer token with "
        "credentials:revoke is required. Revocation metadata is permanent "
        "application state and an audit event is appended."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: {
            "model": ApiErrorResponse,
            "description": "Bearer authentication is missing or invalid.",
        },
        403: {
            "model": ApiErrorResponse,
            "description": "The current user cannot revoke credentials.",
        },
        404: {
            "model": ApiErrorResponse,
            "description": "The active stored credential does not exist.",
        },
        409: {
            "model": ApiErrorResponse,
            "description": "The credential was already revoked or changed.",
        },
        413: ERROR_RESPONSES[413],
        422: ERROR_RESPONSES[422],
        500: ERROR_RESPONSES[500],
        503: {
            "model": ApiErrorResponse,
            "description": "MongoDB persistence is unavailable.",
        },
    },
)
def revoke_credential(
    credential_id: Annotated[
        str,
        Path(min_length=1, max_length=2_048),
    ],
    payload: CredentialRevocationRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_REVOKE)
    ),
    service: CredentialRevocationService = Depends(
        get_credential_revocation_service
    ),
) -> CredentialStatusResponse:
    result = service.revoke(
        credential_id,
        reason=payload.reason,
        revoked_by=principal.id,
        correlation_id=request.state.request_id,
    )
    return CredentialStatusResponse.from_domain(result)


@router.get(
    "/{credential_id}/status",
    response_model=CredentialStatusResponse,
    summary="Read the current stored credential status",
    description=(
        "Returns the persisted lifecycle status and revocation metadata for "
        "one credential. This status lookup is public for verifier use and "
        "appends a STATUS_CHECKED audit event. Expired active/suspended "
        "records are atomically transitioned to EXPIRED."
    ),
    responses={
        404: {
            "model": ApiErrorResponse,
            "description": "The active stored credential does not exist.",
        },
        409: {
            "model": ApiErrorResponse,
            "description": "The credential status changed concurrently.",
        },
        500: ERROR_RESPONSES[500],
        503: {
            "model": ApiErrorResponse,
            "description": "MongoDB persistence is unavailable.",
        },
    },
)
def credential_status(
    credential_id: Annotated[
        str,
        Path(min_length=1, max_length=2_048),
    ],
    request: Request,
    service: CredentialRevocationService = Depends(
        get_credential_revocation_service
    ),
) -> CredentialStatusResponse:
    result = service.get_status(
        credential_id,
        correlation_id=request.state.request_id,
    )
    return CredentialStatusResponse.from_domain(result)


@router.get(
    "/capabilities",
    response_model=CredentialCapabilitiesResponse,
    summary="Describe local credential capabilities",
    description=(
        "Reports the bounded features and explicit limitations of this local "
        "academic prototype without exposing sensitive configuration."
    ),
    responses={500: ERROR_RESPONSES[500]},
)
def credential_capabilities() -> CredentialCapabilitiesResponse:
    return CredentialCapabilitiesResponse(
        service="identity-service",
        api_version="v1",
        credential_model="W3C VC Data Model 2.0 local profile",
        proof_type="DataIntegrityProof",
        cryptosuites=["eddsa-jcs-2022"],
        did_methods=DidMethodsResponse(
            issuer=["did:web"],
            holder_fixtures=["did:key"],
        ),
        operations=CredentialOperationsResponse(
            validation_supported=True,
            sign=True,
            verify=True,
            persist=True,
            revoke=True,
            present=True,
        ),
        limitations=[
            "local academic prototype",
            "credential signing requires local Bearer RBAC",
            "local fixture DID resolution only",
            "synthetic issuer key",
            "no production KMS or HSM",
            "issuance requires MongoDB persistence",
            "status assignment is limited to revocation purpose",
            "no external W3C status-list conformance certification",
            "no JSON-LD RDF canonicalization",
            "presentation exchange and selective disclosure are unsupported",
        ],
    )
