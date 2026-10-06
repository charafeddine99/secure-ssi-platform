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
from app.domain.dcql import (
    MalformedDcqlQueryError,
    UnsupportedDcqlFeatureError,
)
from app.schemas.oid4_api import (
    CreateVerificationSessionRequest,
    VerificationSessionResponse,
    DirectPostRequest,
    DirectPostResponse,
    RejectVerificationSessionRequest,
    RejectVerificationSessionResponse,
    CreateOid4vpPresentationRequest,
    CreateOid4vpPresentationResponse,
    EvaluateDcqlRequest,
    EvaluateDcqlResponse,
    RecordConsentRequest,
    RecordConsentResponse,
)

router = APIRouter(prefix="/oid4vp", tags=["oid4vp"])

@router.post(
    "/requests",
    response_model=VerificationSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create OID4VP Verification Session",
    description="Verifier creates an OpenID4VP 1.0 session with DCQL query, challenge nonce, and openid4vp:// URI."
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
    try:
        session = service.create_session(
            verifier_did=principal.id if principal.id.startswith("did:") else "did:web:verifier.platform.eudi",
            client_id=f"{base_url}/verifier",
            purpose=payload.purpose,
            requested_credential_types=tuple(payload.requested_credential_types),
            requested_fields=tuple(payload.requested_fields),
            dcql_query=payload.dcql_query,
            ttl_seconds=payload.ttl_seconds,
        )
    except (MalformedDcqlQueryError, UnsupportedDcqlFeatureError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    auth_uri = session.to_authorization_request_uri()
    return VerificationSessionResponse(
        session_id=session.session_id,
        verifier_did=session.verifier_did,
        client_id=session.client_id,
        response_uri=session.response_uri,
        nonce=session.nonce,
        dcql_query=dict(session.dcql_query),
        presentation_definition=dict(session.presentation_definition),
        status=session.status.value,
        deep_link_uri=auth_uri,
        qr_payload=auth_uri,
        expires_at=session.expires_at,
        purpose=session.purpose,
        consent_status=session.consent_status,
        rejection_reason=session.rejection_reason,
        requested_fields=list(session.requested_fields),
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
        dcql_query=dict(session.dcql_query),
        presentation_definition=dict(session.presentation_definition),
        status=session.status.value,
        deep_link_uri=auth_uri,
        qr_payload=auth_uri,
        expires_at=session.expires_at,
        purpose=session.purpose,
        consent_status=session.consent_status,
        rejection_reason=session.rejection_reason,
        requested_fields=list(session.requested_fields),
        verification_result=session.verification_result.to_dict() if session.verification_result else None,
        disclosed_claims=dict(session.disclosed_claims) if session.disclosed_claims else None,
    )

@router.post(
    "/requests/{session_id}/evaluate-dcql",
    response_model=EvaluateDcqlResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Wallet Credentials Against Session DCQL Query",
    description="Holder wallet evaluates candidate credentials against the session DCQL query to identify matches for consent."
)
def evaluate_session_dcql(
    session_id: str,
    payload: EvaluateDcqlRequest,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> EvaluateDcqlResponse:
    try:
        eval_result = service.evaluate_wallet_credentials(
            session_id=session_id,
            candidate_credentials=payload.candidate_credentials,
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e
    except (MalformedDcqlQueryError, UnsupportedDcqlFeatureError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return EvaluateDcqlResponse(
        is_satisfied=eval_result.is_satisfied,
        matched_credentials=[
            {
                "query_id": m.query_id,
                "credential_id": m.credential_id,
                "matched_claims": dict(m.matched_claims),
            }
            for m in eval_result.matched_credentials
        ],
        unsatisfied_reason=eval_result.unsatisfied_reason,
        details=dict(eval_result.details),
    )

@router.post(
    "/requests/{session_id}/reject",
    response_model=RejectVerificationSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject OID4VP Verification Session (Holder Consent Denial)",
    description="Holder explicitly declines to provide consent for verification, closing the session with an audit trail."
)
def reject_verification_session(
    session_id: str,
    payload: RejectVerificationSessionRequest,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> RejectVerificationSessionResponse:
    try:
        session = service.reject_session(
            session_id=session_id,
            reason=payload.reason,
            actor_id=payload.holder_did,
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e
    except SessionAlreadyConsumedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    return RejectVerificationSessionResponse(
        session_id=session.session_id,
        status=session.status.value,
        consent_status=session.consent_status or "REJECTED",
        reason=payload.reason,
        rejection_reason=payload.reason,
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
            client_ip=payload.client_ip,
            user_agent=payload.user_agent,
            device_fingerprint=payload.device_fingerprint,
            device_fingerprint_match=payload.device_fingerprint_match,
            is_tor_or_proxy=payload.is_tor_or_proxy,
            failed_attempts=payload.failed_attempts,
            geo_distance_km=payload.geo_distance_km,
            time_since_last_action_sec=payload.time_since_last_action_sec,
            presentation_frequency_10m=payload.presentation_frequency_10m,
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


@router.post(
    "/requests/{session_id}/consent",
    response_model=RecordConsentResponse,
    status_code=status.HTTP_200_OK,
    summary="Record Holder Presentation Consent Decision",
    description="Holder explicitly records an authoritative consent decision (APPROVE or REJECT) bound to session, claims, and credentials."
)
def record_presentation_consent(
    session_id: str,
    payload: RecordConsentRequest,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> RecordConsentResponse:
    try:
        session, decision = service.record_consent(
            session_id=session_id,
            action=payload.action,
            holder_did=payload.holder_did,
            approved_credentials=payload.approved_credentials,
            approved_claims=payload.approved_claims,
            rejected_claims=payload.rejected_claims,
            verifier_did=payload.verifier_did,
            client_id=payload.client_id,
            nonce=payload.nonce,
            purpose=payload.purpose,
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e
    except SessionAlreadyConsumedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return RecordConsentResponse(
        session_id=session.session_id,
        status=session.status.value,
        consent_status=session.consent_status or decision.action.value,
        decision_id=decision.decision_id,
        action=decision.action.value,
        holder_did=decision.holder_did,
        approved_credentials=list(decision.approved_credentials),
        approved_claims=dict(decision.approved_claims),
        rejected_claims=list(decision.rejected_claims),
        timestamp=decision.timestamp,
        rejection_reason=session.rejection_reason,
    )

@router.post(
    "/presentation",
    response_model=CreateOid4vpPresentationResponse,
    status_code=status.HTTP_200_OK,
    summary="Create Signed OID4VP Verifiable Presentation",
    description="Holder wallet requests cryptographic signing of a Verifiable Presentation bound to an active session nonce and verifier audience."
)
def create_oid4vp_presentation(
    payload: CreateOid4vpPresentationRequest,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> CreateOid4vpPresentationResponse:
    try:
        vp_token = service.create_presentation_for_session(
            session_id=payload.session_id,
            verifiable_credentials=payload.verifiable_credentials,
            disclosed_claims=payload.disclosed_claims,
            holder_did=payload.holder_did,
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e
    except SessionAlreadyConsumedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return CreateOid4vpPresentationResponse(
        session_id=payload.session_id,
        vp_token=vp_token,
    )

