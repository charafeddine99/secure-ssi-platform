from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import re
from urllib.parse import urlencode, urlparse
from app.config.public_origin_settings import load_public_origin_settings
from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from app.application.services.request_uri_resolver import RequestUriResolver, request_uri_for
from app.config.request_object_settings import request_object_signer
from app.domain.request_object import CLIENT_ID_PREFIX, REQUEST_OBJECT_MEDIA_TYPE, RequestObjectError
from app.infrastructure.clients.request_uri_fetcher import fetch_request_object

from app.api.v1.dependencies import (
    get_holder_presentation_service,
    get_holder_wallet_service,
    get_oid4vp_service,
    require_permission,
)
from app.application.services.oid4vp_service import Oid4vpService
from app.application.services.holder_wallet_service import HolderWalletService
from app.application.services.presentation_service import HolderPresentationService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission, Role
from app.domain.oid4vp import (
    SessionNotFoundError,
    SessionExpiredError,
    SessionAlreadyConsumedError,
    VerificationSessionStatus,
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
    CreateOid4vpPresentationRequest,
    CreateOid4vpPresentationResponse,
    EvaluateDcqlRequest,
    EvaluateDcqlResponse,
    RecordConsentRequest,
    RecordConsentResponse,
    WalletOid4vpConsentRequest,
    CreateWalletOid4vpPresentationRequest,
    HolderOid4vpRequestResponse,
    VerificationSessionListResponse,
    ResolveRequestUriRequest,
    ResolveRequestUriResponse,
)

_SESSION_HANDLE = re.compile(r"^session_[A-Za-z0-9_-]{8,128}$")

_PUBLIC_ORIGIN = load_public_origin_settings()
router = APIRouter(prefix="/oid4vp", tags=["oid4vp"])


_FORWARDED_HOST = re.compile(r"[A-Za-z0-9.-]{1,253}(:[0-9]{1,5})?")


def _origin(request: Request) -> str:
    # Never the internal service address when a public one exists. Without one,
    # use the address the caller reached the gateway on (set by the gateway, not
    # passed through from clients) rather than the internal Docker hostname.
    if _PUBLIC_ORIGIN.origin:
        return _PUBLIC_ORIGIN.origin
    host = request.headers.get("x-forwarded-host", "")
    proto = request.headers.get("x-forwarded-proto", "")
    if _FORWARDED_HOST.fullmatch(host) and proto in {"http", "https"}:
        return f"{proto}://{host}"
    return str(request.base_url).rstrip("/")


def _deep_link(session, request: Request) -> str:
    """openid4vp:// link. Signed sessions carry only client_id and request_uri."""
    if session.client_id.startswith(CLIENT_ID_PREFIX):
        query = urlencode(
            {
                "client_id": session.client_id,
                "request_uri": request_uri_for(_origin(request), session.session_id),
            }
        )
        return f"openid4vp://?{query}"
    return session.to_authorization_request_uri()


@router.get(
    "/request-objects/{session_id}",
    summary="Signed authorization request (request_uri target)",
    description=(
        "Returns the request as a JWS with typ oauth-authz-req+jwt (OpenID4VP 1.0 "
        "and RFC 9101). Public: a wallet fetches it after scanning. Holds no "
        "credential data, only what the openid4vp link already exposed."
    ),
    responses={200: {"content": {REQUEST_OBJECT_MEDIA_TYPE: {}}}, 404: {}, 410: {}},
)
def get_request_object(
    session_id: str,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> Response:
    if not _SESSION_HANDLE.fullmatch(session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    try:
        token = service.request_object(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.") from error
    except (SessionExpiredError, SessionAlreadyConsumedError) as error:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Request is no longer open.") from error
    return Response(
        content=token,
        media_type=REQUEST_OBJECT_MEDIA_TYPE,
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/wallet/resolve-request",
    response_model=ResolveRequestUriResponse,
    summary="Resolve a scanned openid4vp:// link with request_uri",
    description=(
        "Holder only. Reads the request object (own origin locally, other hosts "
        "through an SSRF-safe fetch), verifies its signature and parameters, and "
        "returns the session to open. Requests from verifiers outside this "
        "platform are refused after verification."
    ),
)
def resolve_request_uri(
    payload: ResolveRequestUriRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_CREATE)
    ),
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> ResolveRequestUriResponse:
    if Role.HOLDER not in principal.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Holder role is required.")
    resolver = RequestUriResolver(
        oid4vp_service=service,
        signer=request_object_signer(),
        own_origins={_origin(request), str(request.base_url).rstrip("/")},
        fetch=fetch_request_object,
    )
    try:
        resolved = resolver.resolve(payload.link)
    except RequestObjectError as error:
        code = (
            status.HTTP_404_NOT_FOUND
            if error.code == "REQUEST_NOT_FOUND"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=f"{error.code}: {error}") from error
    except SessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="REQUEST_NOT_FOUND: This request is not known.",
        ) from error
    except (SessionExpiredError, SessionAlreadyConsumedError) as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="EXPIRED: This request is no longer open.",
        ) from error
    return ResolveRequestUriResponse(session_id=resolved.session_id, client_id=resolved.client_id)


@router.get(
    "/requests",
    response_model=VerificationSessionListResponse,
    summary="List the authenticated verifier's own request history",
    description=(
        "Owner-scoped history with bounded offset pagination. The authenticated "
        "user ID is the persistence filter; client-provided owner or organization "
        "identifiers are not accepted."
    ),
)
def list_verification_sessions(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_VERIFY)
    ),
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> VerificationSessionListResponse:
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verification session pagination is out of range.",
        )
    sessions = service.list_sessions_for_owner(
        owner_user_id=principal.id,
        limit=limit + 1,
        offset=offset,
    )
    has_more = len(sessions) > limit
    items = []
    for session in sessions[:limit]:
        auth_uri = _deep_link(session, request)
        items.append(
            VerificationSessionResponse(
                session_id=session.session_id,
                verifier_did=session.verifier_did,
                client_id=session.client_id,
                response_uri=session.response_uri,
                nonce=session.nonce,
                dcql_query=dict(session.dcql_query),
                presentation_definition=dict(session.presentation_definition),
                status=session.status.value,
                deep_link_uri=auth_uri,
                qr_payload=_PUBLIC_ORIGIN.handoff_uri(session.session_id) or auth_uri,
                handoff_uri=_PUBLIC_ORIGIN.handoff_uri(session.session_id),
                expires_at=session.expires_at,
                purpose=session.purpose,
                consent_status=session.consent_status,
                rejection_reason=session.rejection_reason,
                requested_fields=list(session.requested_fields),
                verification_result=(
                    session.verification_result.to_dict()
                    if session.verification_result
                    else None
                ),
                disclosed_claims=(
                    dict(session.disclosed_claims)
                    if session.disclosed_claims
                    else None
                ),
            )
        )
    return VerificationSessionListResponse(
        items=items,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )

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
    signer = request_object_signer()
    try:
        session = service.create_session(
            owner_user_id=principal.id,
            verifier_did=principal.id if principal.id.startswith("did:") else "did:web:verifier.platform.eudi",
            # Signed requests (JAR): the client_id names the verifier's key.
            client_id=signer.client_id,
            purpose=payload.purpose,
            requested_credential_types=tuple(payload.requested_credential_types),
            requested_fields=tuple(payload.requested_fields),
            dcql_query=payload.dcql_query,
            ttl_seconds=payload.ttl_seconds,
        )
    except (MalformedDcqlQueryError, UnsupportedDcqlFeatureError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    auth_uri = _deep_link(session, request)
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
        qr_payload=_PUBLIC_ORIGIN.handoff_uri(session.session_id) or auth_uri,
        handoff_uri=_PUBLIC_ORIGIN.handoff_uri(session.session_id),
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
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_VERIFY)
    ),
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> VerificationSessionResponse:
    try:
        session = service.get_session_for_owner(
            session_id,
            owner_user_id=principal.id,
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SessionExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e)) from e

    auth_uri = _deep_link(session, request)
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
        qr_payload=_PUBLIC_ORIGIN.handoff_uri(session.session_id) or auth_uri,
        handoff_uri=_PUBLIC_ORIGIN.handoff_uri(session.session_id),
        expires_at=session.expires_at,
        purpose=session.purpose,
        consent_status=session.consent_status,
        rejection_reason=session.rejection_reason,
        requested_fields=list(session.requested_fields),
        verification_result=session.verification_result.to_dict() if session.verification_result else None,
        disclosed_claims=dict(session.disclosed_claims) if session.disclosed_claims else None,
    )


@router.get(
    "/requests/{session_id}/holder-request",
    response_model=HolderOid4vpRequestResponse,
    summary="Get the protocol request for an authenticated Holder wallet",
)
def get_holder_oid4vp_request(
    session_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_CREATE)
    ),
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> HolderOid4vpRequestResponse:
    if Role.HOLDER not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Holder role is required to inspect a presentation request.",
        )
    try:
        session = service.get_session(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification request not found.",
        ) from error
    except SessionExpiredError as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Verification request has expired.",
        ) from error
    if session.status != VerificationSessionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification request not found.",
        )
    auth_uri = _deep_link(session, request)
    return HolderOid4vpRequestResponse(
        session_id=session.session_id,
        verifier_did=session.verifier_did,
        client_id=session.client_id,
        response_uri=session.response_uri,
        nonce=session.nonce,
        dcql_query=dict(session.dcql_query),
        presentation_definition=dict(session.presentation_definition),
        status=session.status.value,
        consent_status=session.consent_status,
        deep_link_uri=auth_uri,
        qr_payload=_PUBLIC_ORIGIN.handoff_uri(session.session_id) or auth_uri,
        handoff_uri=_PUBLIC_ORIGIN.handoff_uri(session.session_id),
        expires_at=session.expires_at,
        purpose=session.purpose,
        requested_fields=list(session.requested_fields),
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
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_CREATE)
    ),
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> EvaluateDcqlResponse:
    if Role.HOLDER not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Holder role is required to evaluate wallet credentials.",
        )
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
                "queryId": m.query_id,
                "credentialId": m.credential_id,
                "matchedClaims": dict(m.matched_claims),
            }
            for m in eval_result.matched_credentials
        ],
        unsatisfied_reason=eval_result.unsatisfied_reason,
        details=dict(eval_result.details),
    )

@router.post(
    "/requests/{session_id}/reject",
    response_model=None,
    status_code=status.HTTP_410_GONE,
    summary="Reject OID4VP Verification Session (Holder Consent Denial)",
    description="Retired insecure route. Use the authenticated wallet-consent endpoint.",
    deprecated=True,
)
def reject_verification_session(
    session_id: str,
    payload: RejectVerificationSessionRequest,
) -> None:
    del session_id, payload
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This legacy route is disabled. Submit a wallet-bound REJECT decision to /wallet-consent.",
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
    request: Request,
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> DirectPostResponse:
    try:
        result = service.process_direct_post(
            session_id=payload.session_id,
            vp_token=payload.vp_token,
            disclosed_claims=payload.disclosed_claims,
            # Risk scores and behavioral telemetry are server-owned. Keep the
            # legacy request fields parseable for older clients, but never let
            # a holder choose the score or claim trusted risk signals.
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
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
    response_model=None,
    status_code=status.HTTP_410_GONE,
    summary="Record Holder Presentation Consent Decision",
    description="Retired insecure route. Use the authenticated wallet-consent endpoint.",
    deprecated=True,
)
def record_presentation_consent(
    session_id: str,
    payload: RecordConsentRequest,
) -> None:
    del session_id, payload
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This legacy route is disabled. Use the authenticated wallet-bound /wallet-consent route.",
    )

@router.post(
    "/presentation",
    response_model=None,
    status_code=status.HTTP_410_GONE,
    summary="Create Signed OID4VP Verifiable Presentation",
    description="Retired insecure signer route. Use the authenticated wallet-presentation endpoint.",
    deprecated=True,
)
def create_oid4vp_presentation(
    payload: CreateOid4vpPresentationRequest,
) -> None:
    del payload
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This legacy signer route is disabled. Use the authenticated wallet-presentation route.",
    )


@router.post(
    "/requests/{session_id}/wallet-consent",
    response_model=RecordConsentResponse,
    status_code=status.HTTP_200_OK,
    summary="Record consent from an authenticated, owned holder wallet",
)
def record_wallet_presentation_consent(
    session_id: str,
    payload: WalletOid4vpConsentRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_CREATE)
    ),
    wallets: HolderWalletService = Depends(get_holder_wallet_service),
    service: Oid4vpService = Depends(get_oid4vp_service),
) -> RecordConsentResponse:
    if Role.HOLDER not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Holder role is required to approve a presentation request.",
        )
    wallet = wallets.require_owned_active(
        payload.wallet_id,
        owner_user_id=principal.id,
        correlation_id=f"oid4vp-consent:{session_id}",
    )
    try:
        session = service.get_session(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SessionExpiredError as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=str(error),
        ) from error
    if payload.holder_did != wallet.holder_did:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The consent holder does not match the authenticated wallet.",
        )

    approved_credentials = tuple(payload.approved_credentials)
    approved_claims = dict(payload.approved_claims)
    rejected_claims = tuple(payload.rejected_claims)
    action = payload.action or payload.decision
    if action == "APPROVE":
        wallet_records = wallets.list_credentials(
            wallet.wallet_id,
            owner_user_id=principal.id,
        )
        wallet_documents = [
            dict(record.raw_credential)
            for record in wallet_records
            if record.raw_credential is not None
        ]
        try:
            evaluation = service.evaluate_wallet_credentials(
                session_id,
                wallet_documents,
            )
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        except SessionExpiredError as error:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=str(error),
            ) from error
        matched_ids = {
            match.credential_id for match in evaluation.matched_credentials
        }
        if not evaluation.is_satisfied or not approved_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The holder wallet does not satisfy the requested DCQL query.",
            )
        if len(set(approved_credentials)) != len(approved_credentials) or not set(
            approved_credentials
        ).issubset(matched_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consent references a credential outside the wallet's DCQL matches.",
            )
        selected_documents = {
            str(document.get("id")): document
            for document in wallet_documents
            if document.get("id") in set(approved_credentials)
        }
        available_claims: dict[str, Any] = {}
        conflicting_claims: set[str] = set()
        for document in selected_documents.values():
            subject = document.get("credentialSubject")
            if isinstance(subject, dict):
                for key, value in subject.items():
                    if key == "id":
                        continue
                    if key in available_claims and available_claims[key] != value:
                        conflicting_claims.add(key)
                    available_claims[key] = value
        if conflicting_claims:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected credentials contain overlapping claims with different values; this profile cannot safely present them together.",
            )
        if (
            rejected_claims
            or set(approved_claims) != set(available_claims)
            or any(
                approved_claims.get(key) != value
                for key, value in available_claims.items()
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This profile presents the complete signed credential. Approve every claim in the selected credential or reject the request; claim-level selective disclosure is not supported.",
            )
    elif action != "REJECT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent decision must be APPROVE or REJECT.",
        )

    try:
        updated, decision = service.record_consent(
            session_id=session_id,
            action=action,
            holder_did=wallet.holder_did,
            approved_credentials=approved_credentials,
            approved_claims=approved_claims,
            rejected_claims=rejected_claims,
            rejection_reason=payload.rejection_reason,
            verifier_did=session.verifier_did,
            client_id=session.client_id,
            nonce=session.nonce,
            purpose=session.purpose,
        )
    except SessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except SessionExpiredError as error:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(error)) from error
    except SessionAlreadyConsumedError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return RecordConsentResponse(
        session_id=updated.session_id,
        status=updated.status.value,
        consent_status=updated.consent_status or decision.action.value,
        decision_id=decision.decision_id,
        action=decision.action.value,
        holder_did=decision.holder_did,
        approved_credentials=list(decision.approved_credentials),
        approved_claims=dict(decision.approved_claims),
        rejected_claims=list(decision.rejected_claims),
        timestamp=decision.timestamp,
        rejection_reason=updated.rejection_reason,
    )


@router.post(
    "/wallet-presentation",
    response_model=CreateOid4vpPresentationResponse,
    summary="Create a session-bound presentation from an owned wallet",
)
def create_wallet_oid4vp_presentation(
    payload: CreateWalletOid4vpPresentationRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.PRESENTATIONS_CREATE)
    ),
    wallets: HolderWalletService = Depends(get_holder_wallet_service),
    sessions: Oid4vpService = Depends(get_oid4vp_service),
    presentations: HolderPresentationService = Depends(
        get_holder_presentation_service
    ),
) -> CreateOid4vpPresentationResponse:
    if Role.HOLDER not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Holder role is required to create a wallet presentation.",
        )
    wallet = wallets.require_owned_active(
        payload.wallet_id,
        owner_user_id=principal.id,
        correlation_id=request.state.request_id,
    )
    try:
        session = sessions.get_session(payload.session_id)
    except SessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SessionExpiredError as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=str(error),
        ) from error
    consent = session.consent_decision
    if consent is None or not consent.user_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An approved wallet-bound consent decision is required.",
        )
    if consent.holder_did != wallet.holder_did:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The authenticated wallet does not match the consent decision.",
        )
    if (
        not payload.credential_ids
        or len(set(payload.credential_ids)) != len(payload.credential_ids)
        or not set(payload.credential_ids).issubset(
            set(consent.approved_credentials)
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected credentials exceed the holder's consent decision.",
        )
    disclosed_claims = dict(payload.disclosed_claims)
    if (
        set(disclosed_claims) != set(consent.approved_claims)
        or any(
            consent.approved_claims.get(key) != value
            for key, value in disclosed_claims.items()
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The presentation must disclose exactly the claims approved with the complete credential.",
        )
    now = datetime.now(UTC)
    remaining = int((session.expires_at - now).total_seconds())
    if remaining < 30:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The verification session expires too soon for presentation.",
        )
    # OpenID4VP 1.0 (Data Integrity): challenge = nonce, domain = client_id.
    # Older sessions with a URL client_id keep the host form they were made with.
    if session.client_id.startswith(CLIENT_ID_PREFIX):
        proof_domain = session.client_id
    else:
        verifier_url = urlparse(session.client_id)
        if not verifier_url.hostname:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The verifier client identifier is not a valid URL.",
            )
        proof_domain = verifier_url.hostname
    try:
        persisted = presentations.create_for_oid4vp_session(
            payload.credential_ids,
            session_id=session.session_id,
            wallet_id=wallet.wallet_id,
            challenge=session.nonce,
            domain=proof_domain,
            audience=session.client_id,
            lifetime_seconds=min(remaining, 600),
            actor_id=principal.id,
            correlation_id=request.state.request_id,
            expected_holder_did=consent.holder_did,
        )
    except SessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except SessionExpiredError as error:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(error)) from error
    except SessionAlreadyConsumedError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return CreateOid4vpPresentationResponse(
        session_id=session.session_id,
        vp_token=dict(persisted.document),
    )

