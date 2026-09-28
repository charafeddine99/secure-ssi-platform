from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Mapping
from bson import ObjectId

from app.application.ports.holder_wallet import HolderWalletRepository
from app.application.ports.oid4vci_repository import CredentialOfferRepository
from app.application.ports.repositories import CredentialRepository
from app.application.services.credential_api_service import CredentialApiService
from app.application.services.status_list_service import StatusListService
from app.domain.oid4vci import (
    CredentialOffer,
    OfferStatus,
    OfferNotFoundError,
    OfferAlreadyClaimedError,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    PersistedCredential,
)
from app.domain.credential_status import CredentialStatus
from app.infrastructure.persistence.repositories import MongoAuditEventRepository
from app.infrastructure.persistence.mappers import new_object_id

DEFAULT_ISSUER_DID = "did:web:issuer.example"

class Oid4vciService:
    def __init__(
        self,
        *,
        offer_repository: CredentialOfferRepository,
        credential_repository: CredentialRepository,
        audit_repository: MongoAuditEventRepository,
        status_list_service: StatusListService,
        credential_issuance_service: CredentialApiService,
        wallet_repository: HolderWalletRepository | None = None,
        base_issuer_url: str = "http://localhost:8001",
    ) -> None:
        self._offers = offer_repository
        self._credentials = credential_repository
        self._audits = audit_repository
        self._status_list = status_list_service
        self._issuance = credential_issuance_service
        self._wallets = wallet_repository
        self._base_issuer_url = base_issuer_url.rstrip("/")

    def get_issuer_metadata(self) -> dict[str, Any]:
        """
        RFC / OID4VCI draft 13 metadata endpoint response for /.well-known/openid-credential-issuer.
        """
        return {
            "credential_issuer": self._base_issuer_url,
            "credential_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/credential",
            "batch_credential_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/batch_credential",
            "deferred_credential_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/deferred",
            "display": [
                {
                    "name": "Secure SSI European Trust Framework Issuer",
                    "locale": "en-US",
                    "logo": {
                        "uri": f"{self._base_issuer_url}/assets/logo.png",
                        "alt_text": "Secure SSI Issuer"
                    }
                }
            ],
            "credential_configurations_supported": {
                "QualifiedElectronicAttestationCredential": {
                    "format": "ldp_vc",
                    "scope": "qeaa",
                    "cryptographic_binding_methods_supported": ["did:key"],
                    "credential_signing_alg_values_supported": ["Ed25519"],
                    "display": [{"name": "Qualified Electronic Attestation Credential (QEAA)", "locale": "en-US"}]
                },
                "NationalIdCredential": {
                    "format": "ldp_vc",
                    "scope": "national_id",
                    "cryptographic_binding_methods_supported": ["did:key"],
                    "credential_signing_alg_values_supported": ["Ed25519"],
                    "display": [{"name": "National Identity Card", "locale": "en-US"}]
                },
                "UniversityAffiliationCredential": {
                    "format": "ldp_vc",
                    "scope": "university_affiliation",
                    "cryptographic_binding_methods_supported": ["did:key"],
                    "credential_signing_alg_values_supported": ["Ed25519"],
                    "display": [{"name": "Higher Education Affiliation", "locale": "en-US"}]
                },
                "DriverLicenseCredential": {
                    "format": "ldp_vc",
                    "scope": "driver_license",
                    "cryptographic_binding_methods_supported": ["did:key"],
                    "credential_signing_alg_values_supported": ["Ed25519"],
                    "display": [{"name": "Mobile Driver License (mDL)", "locale": "en-US"}]
                }
            }
        }

    def create_offer(
        self,
        *,
        issuer_did: str = DEFAULT_ISSUER_DID,
        credential_configuration_ids: tuple[str, ...],
        subject_data: Mapping[str, Any],
        ttl_seconds: int = 1800,
        user_pin: str | None = None,
    ) -> CredentialOffer:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        offer_id = f"offer_{ObjectId()}"
        pre_authorized_code = secrets.token_urlsafe(32)

        offer = CredentialOffer(
            id=new_object_id(),
            offer_id=offer_id,
            credential_issuer=self._base_issuer_url,
            issuer_did=issuer_did,
            credential_configuration_ids=credential_configuration_ids,
            subject_data=subject_data,
            pre_authorized_code=pre_authorized_code,
            status=OfferStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
            user_pin=user_pin,
            version=1
        )
        return self._offers.add(offer)

    def get_offer(self, offer_id: str) -> CredentialOffer:
        offer = self._offers.get_by_offer_id(offer_id)
        if offer is None:
            raise OfferNotFoundError(f"Credential offer {offer_id} not found.")
        now = datetime.now(timezone.utc)
        if offer.is_expired(now):
            raise OfferNotFoundError(f"Credential offer {offer_id} has expired.")
        return offer

    def list_pending_offers(
        self,
        *,
        holder_did: str | None = None,
        owner_user_id: str | None = None,
        limit: int = 50,
    ) -> tuple[CredentialOffer, ...]:
        holder_dids: list[str] = []
        if holder_did:
            holder_dids.append(holder_did)
        if self._wallets is not None and owner_user_id:
            try:
                owned_wallets = self._wallets.list_by_owner(owner_user_id, limit=limit)
                for w in owned_wallets:
                    if w.holder_did and w.holder_did not in holder_dids:
                        holder_dids.append(w.holder_did)
            except Exception:
                pass
        return self._offers.list_pending(
            holder_dids=holder_dids if holder_dids else None,
            owner_user_id=owner_user_id,
            limit=limit,
        )

    def list_offers_by_issuer(
        self,
        issuer_did: str = DEFAULT_ISSUER_DID,
        *,
        status: OfferStatus | None = None,
        limit: int = 50,
    ) -> tuple[CredentialOffer, ...]:
        return self._offers.list_by_issuer(issuer_did, status=status, limit=limit)

    def claim_offer_and_issue(
        self,
        *,
        pre_authorized_code: str,
        holder_did: str,
        wallet_id: str = "wallet_holder_default",
        user_pin: str | None = None,
        owner_user_id: str | None = None,
    ) -> PersistedCredential:
        offer = self._offers.get_by_pre_authorized_code(pre_authorized_code)
        if offer is None:
            raise OfferNotFoundError("Invalid or expired pre-authorized code.")

        now = datetime.now(timezone.utc)
        if offer.is_expired(now):
            raise OfferNotFoundError("Credential offer has expired.")
        if offer.status == OfferStatus.CLAIMED:
            raise OfferAlreadyClaimedError("Credential offer was already claimed.")
        if offer.user_pin and offer.user_pin != user_pin:
            raise ValueError("Invalid user PIN provided for credential offer.")

        resolved_wallet_id: str | None = wallet_id if wallet_id and wallet_id != "wallet_holder_default" else None
        resolved_owner_id: str | None = owner_user_id
        if self._wallets is not None:
            wallet = None
            if resolved_wallet_id:
                try:
                    wallet = self._wallets.get(resolved_wallet_id)
                except Exception:
                    wallet = None
            if wallet is None:
                try:
                    wallet = self._wallets.get_by_holder_did(holder_did)
                except Exception:
                    wallet = None
            if wallet is not None:
                resolved_wallet_id = wallet.wallet_id
                if not resolved_owner_id:
                    resolved_owner_id = wallet.owner_user_id

        cred_type = offer.credential_configuration_ids[0] if offer.credential_configuration_ids else "UniversityAffiliationCredential"
        cred_uuid = f"urn:uuid:{secrets.token_hex(4)}-{secrets.token_hex(2)}-4{secrets.token_hex(2)[1:]}-a{secrets.token_hex(2)[1:]}-{secrets.token_hex(6)}"

        raw_subj = dict(offer.subject_data)
        subject = {
            "id": holder_did,
            "affiliation": raw_subj.get("affiliation", "student"),
            "programCode": raw_subj.get("programCode", "SYN-CS-2026"),
            "degree": raw_subj.get("degree", "Bachelor of Science"),
            "graduationYear": int(raw_subj.get("graduationYear", 2026)),
        }

        # 1. Build unsigned W3C VC payload adhering strictly to W3C VC 2.0 profile
        unsigned_vc = {
            "@context": [
                "https://www.w3.org/ns/credentials/v2",
                "https://secure-ssi.example/contexts/university-affiliation/v1"
            ],
            "id": cred_uuid,
            "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
            "issuer": offer.issuer_did if offer.issuer_did.startswith("did:web:") else "did:web:synthetic-issuer.local",
            "validFrom": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "validUntil": (now + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "credentialSubject": subject
        }

        # 2. Sign credential via issuance service
        signed_vc = self._issuance.sign_credential(unsigned_vc)

        # 3. Retrieve or construct and persist credential (Gap A fix)
        persisted = self._credentials.get_by_credential_id(cred_uuid)
        if persisted is None:
            import hashlib
            import json

            status_list_id: str | None = None
            status_list_index: int | None = None
            cred_status = signed_vc.get("credentialStatus")
            if isinstance(cred_status, dict):
                status_list_url = str(cred_status.get("statusListCredential", ""))
                if status_list_url:
                    status_list_id = status_list_url.rstrip("/").split("/")[-1]
                idx_raw = cred_status.get("statusListIndex")
                if idx_raw is not None:
                    try:
                        status_list_index = int(idx_raw)
                    except (ValueError, TypeError):
                        status_list_index = None

            persisted = PersistedCredential(
                id=new_object_id(),
                credential_id=cred_uuid,
                issuer_did=unsigned_vc["issuer"],
                holder_did=holder_did,
                credential_type=tuple(unsigned_vc["type"]),
                issuance_date=now,
                expiration_date=now + timedelta(days=365),
                credential_hash=hashlib.sha256(
                    json.dumps(signed_vc, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                status=CredentialStatus.ACTIVE,
                raw_credential=signed_vc,
                status_list_id=status_list_id,
                status_list_index=status_list_index,
                wallet_id=resolved_wallet_id,
                owner_user_id=resolved_owner_id,
                created_at=now,
                updated_at=now,
                version=1
            )
            persisted = self._credentials.add(persisted)

        # 4. Mark offer as claimed in MongoDB
        self._offers.mark_claimed(
            offer.offer_id,
            holder_did=holder_did,
            issued_credential_id=cred_uuid,
            expected_version=offer.version
        )

        # 5. Record audit event
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=AuditEventType.VC_SIGNED,
                subject_id=cred_uuid,
                actor_id=offer.issuer_did,
                correlation_id=f"oid4vci:{offer.offer_id}",
                metadata={
                    "offer_id": offer.offer_id,
                    "holder_did": holder_did,
                    "claim_profile": cred_type,
                    "protocol": "OID4VCI-1.0"
                },
                created_at=now,
                updated_at=now,
                version=1
            )
        )

        return persisted
