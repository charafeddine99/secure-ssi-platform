import base64
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from app.api.v1.dependencies import (
    get_holder_wallet_service,
    get_audit_event_repository,
    get_managed_key_repository,
    require_permission,
    _provider_aware_holder_signer,
)
from app.application.ports.key_management import ManagedKeyRepository
from app.application.ports.repositories import AuditEventRepository
from app.application.services.holder_wallet_service import (
    HolderWalletService,
)
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.schemas.credential_api import ApiErrorResponse
from app.schemas.holder_wallet_api import (
    HolderWalletCreateRequest,
    HolderWalletListResponse,
    HolderWalletResponse,
    WalletCredentialInventoryResponse,
    WalletCredentialResponse,
    HolderActivityResponse,
    HolderActivityEventResponse,
    GuardianRecoveryProofRequest,
    GuardianRecoveryProofResponse,
)


router = APIRouter(prefix="/wallets", tags=["holder-wallets"])
_WALLET_ID_PATTERN = r"^wallet_[A-Za-z0-9_-]{16,80}$"
_ERRORS = {
    401: {"model": ApiErrorResponse},
    403: {"model": ApiErrorResponse},
    404: {
        "model": ApiErrorResponse,
        "description": "The wallet is absent or hidden from this user.",
    },
    409: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}


@router.post(
    "",
    response_model=HolderWalletResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an authenticated holder wallet",
    responses=_ERRORS,
)
def create_wallet(
    _payload: HolderWalletCreateRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_CREATE)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
) -> HolderWalletResponse:
    return HolderWalletResponse.from_domain(
        service.create(
            owner_user_id=principal.id,
            correlation_id=request.state.request_id,
        )
    )


@router.get(
    "",
    response_model=HolderWalletListResponse,
    summary="List the authenticated holder's own wallets",
    description=(
        "Owner-scoped: the owner is the authenticated principal, never a request "
        "parameter. Lets a client find its existing wallet instead of creating a new one."
    ),
    responses=_ERRORS,
)
def list_wallets(
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
) -> HolderWalletListResponse:
    return HolderWalletListResponse(
        items=[
            HolderWalletResponse.from_domain(wallet)
            for wallet in service.list_owned(owner_user_id=principal.id)
        ]
    )


@router.get(
    "/{wallet_id}",
    response_model=HolderWalletResponse,
    summary="Read an owned holder wallet",
    responses=_ERRORS,
)
def get_wallet(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
) -> HolderWalletResponse:
    return HolderWalletResponse.from_domain(
        service.get_owned(wallet_id, owner_user_id=principal.id)
    )


@router.post(
    "/guardian-recovery-proof",
    response_model=GuardianRecoveryProofResponse,
    summary="Sign a challenge-bound Guardian recovery decision",
    responses=_ERRORS,
)
def create_guardian_recovery_proof(
    payload: GuardianRecoveryProofRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    wallets: HolderWalletService = Depends(get_holder_wallet_service),
    managed_keys: ManagedKeyRepository = Depends(get_managed_key_repository),
) -> GuardianRecoveryProofResponse:
    wallet = wallets.get_owned_by_holder_did(
        payload.guardian_did,
        owner_user_id=principal.id,
    )
    wallet.require_usable_for_signing()
    if not wallet.holder_did.startswith("did:key:z"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Guardian recovery signing currently supports Ed25519 did:key wallets.",
        )

    signer = _provider_aware_holder_signer(managed_keys)
    metadata = signer.get_metadata(wallet.key_reference)
    expected_method = f"{wallet.holder_did}#{wallet.holder_did[len('did:key:'):]}"
    if metadata.verification_method != expected_method:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The active wallet key is not bound to the registered Guardian DID.",
        )

    issued_at = datetime.now(UTC)
    claims = {
        "iss": wallet.holder_did,
        "sub": payload.guardian_id,
        "aud": "secure-ssi-platform:guardian-recovery",
        "requestId": payload.request_id,
        "sessionId": payload.session_id,
        "walletId": payload.wallet_id,
        "decision": payload.decision,
        "challenge": payload.challenge,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=120)).timestamp()),
        "jti": secrets.token_urlsafe(18),
    }
    header = {
        "alg": "EdDSA",
        "typ": "guardian-recovery+jwt",
        "kid": metadata.verification_method,
    }

    def encode_segment(value: dict[str, object]) -> str:
        raw = json.dumps(
            value,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    signing_input = f"{encode_segment(header)}.{encode_segment(claims)}"
    signature = signer.sign(
        signing_input.encode("ascii"),
        key_reference=wallet.key_reference,
    )
    proof = (
        f"{signing_input}."
        f"{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"
    )
    return GuardianRecoveryProofResponse(
        guardian_did=wallet.holder_did,
        proof=proof,
    )


@router.get(
    "/{wallet_id}/credentials",
    response_model=WalletCredentialInventoryResponse,
    summary="List credentials owned by a holder wallet",
    responses=_ERRORS,
)
def list_wallet_credentials(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_CREDENTIALS_READ)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
) -> WalletCredentialInventoryResponse:
    records = service.list_credentials(
        wallet_id,
        owner_user_id=principal.id,
    )
    return WalletCredentialInventoryResponse(
        wallet_id=wallet_id,
        credentials=[
            WalletCredentialResponse.from_domain(record)
            for record in records
        ],
    )


@router.get(
    "/{wallet_id}/activity",
    response_model=HolderActivityResponse,
    summary="List activity for an owned Holder wallet",
    description=(
        "Returns a minimal event feed scoped to the authenticated wallet owner, "
        "its Holder DID, and credentials stored in that wallet. Event metadata "
        "and raw credential claims are intentionally omitted."
    ),
    responses=_ERRORS,
)
def list_wallet_activity(
    wallet_id: Annotated[str, Path(pattern=_WALLET_ID_PATTERN)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    service: HolderWalletService = Depends(get_holder_wallet_service),
    audit_events: AuditEventRepository = Depends(get_audit_event_repository),
) -> HolderActivityResponse:
    wallet = service.get_owned(wallet_id, owner_user_id=principal.id)
    credentials = service.list_credentials(
        wallet_id,
        owner_user_id=principal.id,
        limit=500,
    )
    events = audit_events.list_by_actor_or_subject(
        actor_ids=(wallet.holder_did,),
        subject_ids=(
            wallet.wallet_id,
            *(record.credential_id for record in credentials),
        ),
        limit=limit + 1,
        skip=offset,
    )
    has_more = len(events) > limit
    return HolderActivityResponse(
        wallet_id=wallet.wallet_id,
        items=[
            HolderActivityEventResponse(
                event_id=event.id,
                event_type=event.event_type.value,
                subject_id=event.subject_id,
                correlation_id=event.correlation_id,
                created_at=event.created_at,
            )
            for event in events[:limit]
        ],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )
