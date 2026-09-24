from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.api.v1.dependencies import (
    get_oid4vp_service,
    require_permission,
)
from app.application.services.oid4vp_service import Oid4vpService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.oid4vp import (
    SessionNotFoundError,
    SessionExpiredError,
    SessionAlreadyConsumedError,
)
from app.schemas.oid4_api import (
    CreateVerificationSessionRequest,
    VerificationSessionResponse,
    DirectPostRequest,
    DirectPostResponse,
)

router = APIRouter(prefix="/oid4vp", tags=["oid4vp"])

@router.post(
    "/requests",
    response_model=VerificationSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create OID4VP Verification Session",
    description="Verifier creates a presentation definition with challenge nonce and openid4vp:// URI."
)
def create_verification_session(
    payload: CreateVerificationSessionRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_VERIFY)
    ),
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> VerificationSessionResponse:
    base_url = str(request.base_url).rstrip("/")
    session = service.create_session(
        verifier_did=principal.id if principal.id.startswith("did:") else "did:web:verifier.platform.eudi",
        client_id=f"{base_url}/verifier",
        purpose=payload.purpose,
        requested_credential_types=tuple(payload.requested_credential_types),
        requested_fields=tuple(payload.requested_fields),
        ttl_seconds=payload.ttl_seconds,
    )
    auth_uri = session.to_authorization_request_uri()
    return VerificationSessionResponse(
        session_id=session.session_id,
        verifier_did=session.verifier_did,
        client_id=session.client_id,
        response_uri=session.response_uri,
        nonce=session.nonce,
        presentation_definition=dict(session.presentation_definition),
        status=session.status.value,
        deep_link_uri=auth_uri,
        qr_payload=auth_uri,
        expires_at=session.expires_at,
        verification_result=session.verification_result.to_dict() if session.verification_result else None,
        disclosed_claims=dict(session.disclosed_claims) if session.disclosed_claims else None,
    )

@router.get(
    "/requests/{session_id}",
    response_model=VerificationSessionResponse,
    summary="Get Verification Session Status",
    description="Verifier polls this endpoint to detect when holder submits presentation and view the 9-point result."
)
def get_verification_session(
    session_id: str,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> VerificationSessionResponse:
    try:
        session = service.get_session(session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e

    auth_uri = session.to_authorization_request_uri()
    return VerificationSessionResponse(
        session_id=session.session_id,
        verifier_did=session.verifier_did,
        client_id=session.client_id,
        response_uri=session.response_uri,
        nonce=session.nonce,
        presentation_definition=dict(session.presentation_definition),
        status=session.status.value,
        deep_link_uri=auth_uri,
        qr_payload=auth_uri,
        expires_at=session.expires_at,
        verification_result=session.verification_result.to_dict() if session.verification_result else None,
        disclosed_claims=dict(session.disclosed_claims) if session.disclosed_claims else None,
    )

@router.post(
    "/response",
    response_model=DirectPostResponse,
    status_code=status.HTTP_200_OK,
    summary="OID4VP Direct Post Submission",
    description="Holder wallet posts the Verifiable Presentation and disclosed claims to complete verification."
)
def submit_direct_post(
    payload: DirectPostRequest,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> DirectPostResponse:
    try:
        result = service.process_direct_post(
            session_id=payload.session_id,
            vp_token=payload.vp_token,
            disclosed_claims=payload.disclosed_claims,
            ai_risk_score=payload.ai_risk_score,
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e
    except SessionAlreadyConsumedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return DirectPostResponse(
        status="PROCESSED",
        result=result.to_dict(),
    )
