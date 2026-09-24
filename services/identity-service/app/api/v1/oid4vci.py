from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.api.v1.dependencies import (
    get_oid4vci_service,
    require_permission,
)
from app.application.services.oid4vci_service import Oid4vciService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.oid4vci import (
    OfferNotFoundError,
    OfferAlreadyClaimedError,
)
from app.schemas.oid4_api import (
    CreateOfferRequest,
    CredentialOfferResponse,
    ClaimOfferRequest,
    ClaimOfferResponse,
)

router = APIRouter(prefix="/oid4vci", tags=["oid4vci"])

@router.get(
    "/.well-known/openid-credential-issuer",
    summary="OID4VCI Issuer Metadata",
    description="Returns standard OpenID for Verifiable Credential Issuance metadata."
)
def get_issuer_metadata(
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> dict[str, Any]:
    return service.get_issuer_metadata()

@router.post(
    "/offers",
    response_model=CredentialOfferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create OID4VCI Credential Offer",
    description="Issuer generates an openid-credential-offer payload and deep link URI with QR data."
)
def create_credential_offer(
    payload: CreateOfferRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.CREDENTIALS_SIGN)
    ),
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> CredentialOfferResponse:
    offer = service.create_offer(
        issuer_did=principal.id if principal.id.startswith("did:") else "did:web:issuer.example",
        credential_configuration_ids=tuple(payload.credential_configuration_ids),
        subject_data=payload.subject_data,
        ttl_seconds=payload.ttl_seconds,
        user_pin=payload.user_pin,
    )
    base_url = str(request.base_url).rstrip("/")
    deep_link = offer.to_deep_link_uri(base_url)
    return CredentialOfferResponse(
        offer_id=offer.offer_id,
        credential_issuer=offer.credential_issuer,
        credential_configuration_ids=list(offer.credential_configuration_ids),
        pre_authorized_code=offer.pre_authorized_code,
        status=offer.status.value,
        deep_link_uri=deep_link,
        qr_payload=deep_link,
        expires_at=offer.expires_at,
        subject_data=dict(offer.subject_data),
    )

@router.get(
    "/offers/{offer_id}",
    response_model=CredentialOfferResponse,
    summary="Query Credential Offer by ID",
    description="Endpoint invoked by holder wallet to inspect offer before accepting."
)
def get_credential_offer(
    offer_id: str,
    request: Request,
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> CredentialOfferResponse:
    try:
        offer = service.get_offer(offer_id)
    except OfferNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    
    base_url = str(request.base_url).rstrip("/")
    deep_link = offer.to_deep_link_uri(base_url)
    return CredentialOfferResponse(
        offer_id=offer.offer_id,
        credential_issuer=offer.credential_issuer,
        credential_configuration_ids=list(offer.credential_configuration_ids),
        pre_authorized_code=offer.pre_authorized_code,
        status=offer.status.value,
        deep_link_uri=deep_link,
        qr_payload=deep_link,
        expires_at=offer.expires_at,
        subject_data=dict(offer.subject_data),
    )

@router.post(
    "/credential",
    response_model=ClaimOfferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Claim OID4VCI Credential",
    description="Holder wallet exchanges pre-authorized code and provides holder DID to receive signed W3C VC."
)
def claim_credential(
    payload: ClaimOfferRequest,
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> ClaimOfferResponse:
    try:
        credential = service.claim_offer_and_issue(
            pre_authorized_code=payload.pre_authorized_code,
            holder_did=payload.holder_did,
            wallet_id=payload.wallet_id,
            user_pin=payload.user_pin,
        )
    except OfferNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except OfferAlreadyClaimedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return ClaimOfferResponse(
        credential=dict(credential.raw_credential),
        credential_id=credential.credential_id,
        status=credential.status.value,
    )
