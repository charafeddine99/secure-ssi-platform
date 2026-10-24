from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse

from app.api.v1.dependencies import (
    _provider_aware_holder_signer,
    get_current_principal,
    get_authentication_service,
    get_authorization_service,
    get_holder_wallet_service,
    get_managed_key_repository,
    get_oid4vci_service,
    require_permission,
)
from app.application.ports.key_management import ManagedKeyRepository
from app.application.services.authentication_service import AuthenticationService
from app.application.services.authorization_service import AuthorizationService
from app.application.services.oid4vci_service import Oid4vciService
from app.application.services.holder_wallet_service import HolderWalletService
from app.domain.auth import AuthenticatedPrincipal
from app.domain.permissions import Permission
from app.domain.exceptions import PermissionDeniedError
from app.domain.oid4vci import (
    OfferNotFoundError,
    OfferAlreadyClaimedError,
    InvalidGrantError,
    InvalidTokenError,
    InvalidProofError,
    InvalidNonceError,
    UnsupportedProofTypeError,
    UnsupportedCredentialConfigurationError,
    InvalidCredentialSubjectError,
)
from app.schemas.oid4_api import (
    CreateOfferRequest,
    CredentialOfferResponse,
    ClaimOfferRequest,
    ClaimOfferResponse,
    NonceResponse,
    HolderProofRequest,
    HolderProofResponse,
)
from app.api.v1.issuer_scope import require_issuer_did

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
    subj_data = dict(payload.subject_data)
    if payload.recipient_did and "recipient_did" not in subj_data and "holder_did" not in subj_data:
        subj_data["recipient_did"] = payload.recipient_did

    issuer_did = require_issuer_did(principal)
    if not service.supports_issuer(issuer_did):
        raise PermissionDeniedError(
            "This issuer has no configured credential signing key."
        )
    try:
        offer = service.create_offer(
            issuer_did=issuer_did,
            credential_configuration_ids=tuple(payload.credential_configuration_ids),
            subject_data=subj_data,
            ttl_seconds=payload.ttl_seconds,
            user_pin=payload.user_pin,
        )
    except UnsupportedCredentialConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except InvalidCredentialSubjectError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
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
    "/offers",
    response_model=list[CredentialOfferResponse],
    summary="List Pending Credential Offers",
    description="Returns pending credential offers that the authenticated holder is authorized to see."
)
def list_credential_offers(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> list[CredentialOfferResponse]:
    base_url = str(request.base_url).rstrip("/")
    is_issuer = any(
        (r.value if hasattr(r, "value") else str(r)).lower() in {"issuer", "admin"}
        for r in principal.roles
    )

    if is_issuer and request.query_params.get("as_issuer") == "true":
        issuer_did = require_issuer_did(principal)
        offers = service.list_offers_by_issuer(issuer_did=issuer_did)
    else:
        offers = service.list_pending_offers(
            holder_did=principal.id if principal.id.startswith("did:") else None,
            owner_user_id=principal.id,
        )

    responses: list[CredentialOfferResponse] = []
    for offer in offers:
        deep_link = offer.to_deep_link_uri(base_url)
        responses.append(
            CredentialOfferResponse(
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
        )
    return responses

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
    "/token",
    summary="OID4VCI 1.0 Token Endpoint",
    description="Exchanges pre-authorized code for an access token and issuer c_nonce (OID4VCI 1.0 Section 6.1)."
)
async def issue_token(
    request: Request,
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> Any:
    content_type = request.headers.get("content-type", "").lower()
    grant_type = ""
    pre_auth_code = ""
    user_pin: str | None = None
    client_id: str | None = None

    if "application/x-www-form-urlencoded" in content_type:
        raw_body = (await request.body()).decode("utf-8")
        from urllib.parse import parse_qs
        form = parse_qs(raw_body)
        grant_type = form.get("grant_type", [""])[0]
        pre_auth_code = (
            form.get("pre-authorized_code", [""])[0]
            or form.get("pre_authorized_code", [""])[0]
            or form.get("preAuthorizedCode", [""])[0]
        )
        raw_pin = form.get("user_pin", form.get("tx_code", form.get("userPin", [None])))[0]
        user_pin = str(raw_pin) if (raw_pin is not None and not isinstance(raw_pin, str)) else raw_pin
        raw_client = form.get("client_id", form.get("clientId", [None]))[0]
        client_id = str(raw_client) if (raw_client is not None and not isinstance(raw_client, str)) else raw_client
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                grant_type = str(body.get("grant_type", body.get("grantType", "")))
                pre_auth_code = str(body.get("pre-authorized_code", body.get("pre_authorized_code", body.get("preAuthorizedCode", ""))))
                raw_pin = body.get("user_pin", body.get("tx_code", body.get("userPin")))
                user_pin = str(raw_pin) if raw_pin is not None else None
                raw_client = body.get("client_id", body.get("clientId"))
                client_id = str(raw_client) if raw_client is not None else None
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "invalid_request", "error_description": "Failed to parse token request payload."}
            )

    try:
        res = service.exchange_pre_authorized_code_for_token(
            grant_type=grant_type,
            pre_authorized_code=pre_auth_code,
            user_pin=user_pin,
            client_id=client_id,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            content=res,
        )
    except InvalidGrantError as e:
        msg = str(e)
        if ":" in msg:
            parts = msg.split(":", 1)
            err_code = parts[0].strip()
            err_desc = parts[1].strip()
        else:
            err_code = "invalid_grant"
            err_desc = msg
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            content={"error": err_code, "error_description": err_desc}
        )

@router.post(
    "/nonce",
    response_model=NonceResponse,
    summary="OID4VCI 1.0 Nonce Endpoint",
    description="Provides a fresh server-generated c_nonce with 600s lifetime semantics for holder proof binding."
)
def get_c_nonce(
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> NonceResponse:
    res = service.generate_c_nonce()
    return NonceResponse(**res)


@router.post(
    "/holder-proof",
    response_model=HolderProofResponse,
    summary="Sign an OID4VCI holder proof with an owned wallet key",
    description=(
        "Creates an EdDSA JWT proof for the authenticated holder's active "
        "wallet key. The private key remains behind the configured signing "
        "provider. This local prototype operation is not a production custody claim."
    ),
)
def create_holder_proof(
    payload: HolderProofRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    wallets: HolderWalletService = Depends(get_holder_wallet_service),
    managed_keys: ManagedKeyRepository = Depends(get_managed_key_repository),
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> HolderProofResponse:
    wallet = wallets.get_owned(payload.wallet_id, owner_user_id=principal.id)
    wallet.require_usable_for_signing()
    issuer = service.get_issuer_metadata()
    expected_audience = issuer.get("credential_issuer")
    if not isinstance(expected_audience, str) or payload.audience.rstrip("/") != expected_audience.rstrip("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proof audience does not match the configured credential issuer.",
        )

    signer = _provider_aware_holder_signer(managed_keys)
    metadata = signer.get_metadata(wallet.key_reference)
    header = {
        "alg": "EdDSA",
        "typ": "openid4vci-proof+jwt",
        "kid": metadata.verification_method,
    }
    claims = {
        "iss": wallet.holder_did,
        "aud": expected_audience,
        "iat": int(datetime.now(UTC).timestamp()),
        "nonce": payload.nonce,
        "jti": secrets.token_urlsafe(18),
    }

    def encode(value: dict[str, Any]) -> str:
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    signing_input = f"{encode(header)}.{encode(claims)}"
    signature = signer.sign(
        signing_input.encode("ascii"),
        key_reference=wallet.key_reference,
    )
    jwt = f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"
    return HolderProofResponse(holder_did=wallet.holder_did, jwt=jwt)

@router.post(
    "/credential",
    summary="OID4VCI 1.0 Credential Endpoint",
    description="Protected credential endpoint requiring Bearer access token and cryptographic holder proof-of-possession. Also maintains isolated legacy direct pre-authorized code fallback with X-Legacy-Issuance header."
)
async def request_credential(
    request: Request,
    service: Oid4vciService = Depends(get_oid4vci_service),
    legacy_authentication: AuthenticationService = Depends(
        get_authentication_service
    ),
    authorization: AuthorizationService = Depends(get_authorization_service),
    wallets: HolderWalletService = Depends(get_holder_wallet_service),
) -> Any:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}

    pre_auth = body.get("preAuthorizedCode") or body.get("pre_authorized_code")

    # The deprecated compatibility shape is accepted only with an application
    # access token and an owned, active wallet. OID4VCI access tokens are
    # opaque in this implementation, so they cannot authorize this path.
    if pre_auth and auth_header and auth_header.strip().lower().startswith("bearer "):
        bearer_token = auth_header.strip()[7:].strip()
        try:
            legacy_principal = legacy_authentication.authenticate_access_token(
                bearer_token
            )
        except Exception:
            legacy_principal = None
        if legacy_principal is not None:
            authorization.require_permission(
                legacy_principal,
                Permission.WALLETS_READ,
            )
            holder_did = body.get("holderDid") or body.get("holder_did")
            wallet_id = body.get("walletId") or body.get("wallet_id")
            if not holder_did or not wallet_id:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    headers={"X-Legacy-Issuance": "true"},
                    content={"detail": "holderDid and walletId are required for legacy direct issuance."},
                )
            wallet = wallets.require_owned_active(
                wallet_id,
                owner_user_id=legacy_principal.id,
                correlation_id=request.state.request_id,
            )
            if wallet.holder_did != holder_did:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    headers={"X-Legacy-Issuance": "true"},
                    content={"detail": "holderDid does not match the authenticated wallet."},
                )
            try:
                credential = service.claim_offer_and_issue(
                    pre_authorized_code=pre_auth,
                    holder_did=wallet.holder_did,
                    wallet_id=wallet.wallet_id,
                    user_pin=body.get("userPin") or body.get("user_pin"),
                    owner_user_id=legacy_principal.id,
                )
                return JSONResponse(
                    status_code=status.HTTP_201_CREATED,
                    headers={
                        "X-Legacy-Issuance": "true",
                        "Warning": '299 - "Deprecated direct pre-authorized code issuance. Use Token Endpoint and Proof-of-Possession."',
                    },
                    content={
                        "credential": dict(credential.raw_credential or {}),
                        "credential_id": credential.credential_id,
                        "status": credential.status.value,
                    },
                )
            except OfferNotFoundError as e:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    headers={"X-Legacy-Issuance": "true"},
                    content={"detail": str(e)},
                )
            except OfferAlreadyClaimedError as e:
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    headers={"X-Legacy-Issuance": "true"},
                    content={"detail": str(e)},
                )
            except ValueError as e:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    headers={"X-Legacy-Issuance": "true"},
                    content={"detail": str(e)},
                )

    # 1. CANONICAL OID4VCI 1.0 PATH: Bearer access token + Holder Proof-of-Possession
    if auth_header and auth_header.strip().lower().startswith("bearer "):
        access_token = auth_header.strip()[7:].strip()
        if not access_token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="Missing token."'},
                content={"error": "invalid_token", "error_description": "Missing token."},
            )

        cred_config_id = body.get("credential_configuration_id") or body.get("credentialConfigurationId") or body.get("format")
        proof = body.get("proof")
        wallet_id = body.get("wallet_id") or body.get("walletId") or "wallet_holder_default"
        owner_user_id = body.get("owner_user_id") or body.get("ownerUserId")

        try:
            persisted, fresh_nonce, nonce_expires_in = service.issue_credential_with_token(
                access_token=access_token,
                credential_configuration_id=cred_config_id,
                proof=proof,
                wallet_id=wallet_id,
                owner_user_id=owner_user_id,
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "credential": dict(persisted.raw_credential or {}),
                    "c_nonce": fresh_nonce,
                    "c_nonce_expires_in": nonce_expires_in,
                    "status": persisted.status.value,
                }
            )
        except InvalidTokenError as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{str(e)}"'},
                content={"error": "invalid_token", "error_description": str(e)},
            )
        except (InvalidProofError, InvalidNonceError, UnsupportedProofTypeError) as e:
            err_code = "invalid_proof" if isinstance(e, InvalidProofError) else (
                "invalid_nonce" if isinstance(e, InvalidNonceError) else "unsupported_proof_type"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": err_code, "error_description": str(e)},
            )
        except UnsupportedCredentialConfigurationError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "unsupported_credential_configuration_id", "error_description": str(e)},
            )
        except InvalidCredentialSubjectError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "invalid_credential_request", "error_description": str(e)},
            )
        except OfferNotFoundError as e:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "invalid_request", "error_description": str(e)},
            )

    # 3. Neither Bearer token nor legacy preAuthorizedCode provided
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="Authorization Bearer token is required."'},
        content={"error": "invalid_token", "error_description": "Authorization Bearer token is required."},
    )

@router.post(
    "/legacy/claim",
    response_model=ClaimOfferResponse,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    summary="Legacy Direct Credential Claim (Deprecated)",
    description="Deprecated non-standard pre-authorized code exchange bypassing Token Endpoint. Maintained strictly for backwards compatibility."
)
def legacy_claim_credential(
    payload: ClaimOfferRequest,
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.WALLETS_READ)
    ),
    wallets: HolderWalletService = Depends(get_holder_wallet_service),
    service: Oid4vciService = Depends(get_oid4vci_service),
) -> ClaimOfferResponse:
    response.headers["X-Legacy-Issuance"] = "true"
    response.headers["Warning"] = '299 - "Deprecated direct pre-authorized code issuance. Use Token Endpoint and Proof-of-Possession."'
    wallet = wallets.require_owned_active(
        payload.wallet_id,
        owner_user_id=principal.id,
        correlation_id=request.state.request_id,
    )
    if wallet.holder_did != payload.holder_did:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="holderDid does not match the authenticated wallet.",
        )
    try:
        credential = service.claim_offer_and_issue(
            pre_authorized_code=payload.pre_authorized_code,
            holder_did=wallet.holder_did,
            wallet_id=wallet.wallet_id,
            user_pin=payload.user_pin,
            owner_user_id=principal.id,
        )
    except OfferNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except OfferAlreadyClaimedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return ClaimOfferResponse(
        credential=dict(credential.raw_credential or {}),
        credential_id=credential.credential_id,
        status=credential.status.value,
    )
