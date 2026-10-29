from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Request, status

from app.api.v1.dependencies import (
    get_credential_api_service,
    get_revocation_anchor_scheduler,
    get_credential_issuance_api_service,
    get_credential_revocation_service,
    require_any_permission,
    require_permission,
)
from app.application.services.credential_api_service import CredentialApiService
from app.application.services.credential_revocation_service import (
    CredentialRevocationService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission, Role
from app.domain.exceptions import PermissionDeniedError
from app.api.v1.issuer_scope import (
    credential_issuer_did,
    issuer_did_for_authorization,
    require_issuer_did,
)
from app.schemas.credential_api import (
    ApiErrorResponse,
    CredentialCapabilitiesResponse,
    CredentialEnvelope,
    CredentialOperationsResponse,
    CredentialRevocationRequest,
    CredentialSignResponse,
    CredentialStatusEventResponse,
    CredentialStatusHistoryResponse,
    CredentialStatusResponse,
    CredentialValidationResponse,
    CredentialVerificationResponse,
    DidMethodsResponse,
)


router = APIRouter(prefix="/credentials", tags=["credentials"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_SIGN)
    ),
    service: CredentialApiService = Depends(
        get_credential_issuance_api_service
    ),
) -> CredentialSignResponse:
    if Role.ADMIN not in principal.roles:
        issuer_did = require_issuer_did(principal)
        if credential_issuer_did(envelope.credential) != issuer_did:
            raise PermissionDeniedError(
                "The credential issuer does not match the authenticated issuer scope."
            )
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
    background_tasks: BackgroundTasks,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_REVOKE)
    ),
    service: CredentialRevocationService = Depends(
        get_credential_revocation_service
    ),
    anchor_revocation: Callable[[str, str], None] | None = Depends(
        get_revocation_anchor_scheduler
    ),
) -> CredentialStatusResponse:
    caller_issuer_did = issuer_did_for_authorization(principal)
    result = service.revoke(
        credential_id,
        reason=payload.reason,
        revoked_by=principal.id,
        correlation_id=request.state.request_id,
        caller_roles=principal.roles,
        caller_issuer_did=caller_issuer_did,
    )
    if anchor_revocation is not None:
        # Digest-only on-chain record; runs after the response and cannot alter it.
        background_tasks.add_task(
            anchor_revocation, result.credential_id, result.revocation_reason or ""
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
    "/{credential_id}/history",
    response_model=CredentialStatusHistoryResponse,
    summary="Read credential lifecycle status and audit history",
    description=(
        "Returns the chronological append-only audit events and lifecycle "
        "history for one credential. Access is authorized only for the "
        "issuing authority or administrator."
    ),
    responses={
        401: {
            "model": ApiErrorResponse,
            "description": "Bearer authentication is missing or invalid.",
        },
        403: {
            "model": ApiErrorResponse,
            "description": "The current user is not authorized to audit this credential.",
        },
        404: {
            "model": ApiErrorResponse,
            "description": "The active stored credential does not exist.",
        },
        500: ERROR_RESPONSES[500],
        503: {
            "model": ApiErrorResponse,
            "description": "MongoDB persistence is unavailable.",
        },
    },
)
def credential_history(
    credential_id: Annotated[
        str,
        Path(min_length=1, max_length=2_048),
    ],
    request: Request,
    # Read-only audit trail: the issuing authority or a platform operator.
    # Object-level scope is enforced in CredentialRevocationService.get_history.
    principal: AuthenticatedPrincipal = Depends(
        require_any_permission(
            Permission.CREDENTIALS_REVOKE,
            Permission.ADMIN_OPERATIONS_READ,
        )
    ),
    service: CredentialRevocationService = Depends(
        get_credential_revocation_service
    ),
) -> CredentialStatusHistoryResponse:
    caller_issuer_did = issuer_did_for_authorization(principal)
    events = service.get_history(
        credential_id,
        actor_id=principal.id,
        caller_roles=principal.roles,
        caller_issuer_did=caller_issuer_did,
    )
    status_snapshot = service.get_status(
        credential_id,
        correlation_id=request.state.request_id,
        actor_id=principal.id,
    )
    return CredentialStatusHistoryResponse(
        credential_id=credential_id,
        current_status=status_snapshot.status,
        events=[
            CredentialStatusEventResponse(
                event_id=ev.id,
                event_type=ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type),
                subject_id=ev.subject_id or "",
                actor_id=ev.actor_id,
                correlation_id=ev.correlation_id,
                created_at=ev.created_at,
                metadata=dict(ev.metadata or {}),
            )
            for ev in events
        ],
        total_events=len(events),
    )


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
