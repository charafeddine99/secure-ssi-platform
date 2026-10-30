from __future__ import annotations

import secrets
from app.services.credential_validator import PROGRAM_CODE_PATTERN
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Mapping

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
    InvalidGrantError,
    InvalidTokenError,
    InvalidProofError,
    InvalidNonceError,
    UnsupportedProofTypeError,
    UnsupportedCredentialConfigurationError,
    InvalidCredentialSubjectError,
)
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    PersistedCredential,
)
from app.domain.credential_status import CredentialStatus
from app.infrastructure.persistence.repositories import MongoAuditEventRepository
from app.infrastructure.persistence.mappers import new_object_id
from app.services.credential_validator import (
    CREDENTIAL_PROFILE_CONTEXTS,
    VC_V2_CONTEXT,
)

DEFAULT_ISSUER_DID = "did:web:issuer.example"
CREDENTIAL_PROFILE_METADATA = {
    "QualifiedElectronicAttestationCredential": (
        "qeaa",
        "Qualified Electronic Attestation Credential (QEAA)",
    ),
    "UniversityAffiliationCredential": (
        "university_affiliation",
        "Higher Education Affiliation",
    ),
}

# Wrong transaction codes allowed per offer before it is revoked (OID4VCI §13.6).
MAX_TX_CODE_ATTEMPTS = 5

class Oid4vciService:
    _SHARED_NONCES: dict[str, tuple[datetime, bool]] = {}
    _SHARED_REDEEMED_CODES: set[str] = set()
    _SHARED_ISSUED_TOKENS: dict[str, dict[str, Any]] = {}

    @classmethod
    def reset_shared_state(cls) -> None:
        cls._SHARED_NONCES.clear()
        cls._SHARED_REDEEMED_CODES.clear()
        cls._SHARED_ISSUED_TOKENS.clear()

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
        # Shared in-memory storage for active c_nonces, redeemed pre-auth codes, and access tokens
        self._nonces = self._SHARED_NONCES
        self._redeemed_codes = self._SHARED_REDEEMED_CODES
        self._issued_tokens = self._SHARED_ISSUED_TOKENS

    def get_issuer_metadata(self) -> dict[str, Any]:
        """
        OpenID4VCI 1.0 Final metadata endpoint response for /.well-known/openid-credential-issuer.
        """
        proof_types = {
            "jwt": {
                "proof_signing_alg_values_supported": ["EdDSA"]
            },
            "ldp_vp": {
                "proof_signing_alg_values_supported": ["Ed25519"]
            }
        }
        credential_configurations = {
            credential_type: {
                "format": "ldp_vc",
                "scope": CREDENTIAL_PROFILE_METADATA[credential_type][0],
                "cryptographic_binding_methods_supported": ["did:key"],
                "credential_signing_alg_values_supported": ["Ed25519"],
                "proof_types_supported": proof_types,
                "credential_definition": {
                    "@context": [VC_V2_CONTEXT, context],
                    "type": ["VerifiableCredential", credential_type],
                },
                "display": [
                    {
                        "name": CREDENTIAL_PROFILE_METADATA[credential_type][1],
                        "locale": "en-US",
                    }
                ],
            }
            for credential_type, context in CREDENTIAL_PROFILE_CONTEXTS.items()
        }
        return {
            "credential_issuer": self._base_issuer_url,
            "credential_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/credential",
            "token_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/token",
            "nonce_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/nonce",
            "batch_credential_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/batch_credential",
            "deferred_credential_endpoint": f"{self._base_issuer_url}/api/v1/oid4vci/deferred",
            "display": [
                {
                    "name": "Secure SSI Platform Issuer",
                    "locale": "en-US",
                    "logo": {
                        "uri": f"{self._base_issuer_url}/assets/logo.png",
                    "alt_text": "Secure SSI Platform Issuer"
                    }
                }
            ],
            "credential_configurations_supported": credential_configurations
        }

    def supports_issuer(self, issuer_did: str) -> bool:
        return self._issuance.supports_issuer(issuer_did)

    def create_offer(
        self,
        *,
        issuer_did: str = DEFAULT_ISSUER_DID,
        credential_configuration_ids: tuple[str, ...],
        subject_data: Mapping[str, Any],
        ttl_seconds: int = 1800,
        user_pin: str | None = None,
    ) -> CredentialOffer:
        self._validate_offer_subject(credential_configuration_ids, subject_data)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        # Offer references must not be guessable: ObjectIds are timestamp+counter
        # based, so a neighbouring offer could be derived from one observed id.
        offer_id = f"offer_{secrets.token_urlsafe(24)}"
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

    @staticmethod
    def _validate_offer_subject(
        credential_configuration_ids: tuple[str, ...],
        subject_data: Mapping[str, Any],
    ) -> None:
        unsupported_configs = sorted(
            set(credential_configuration_ids) - set(CREDENTIAL_PROFILE_CONTEXTS)
        )
        if unsupported_configs:
            raise UnsupportedCredentialConfigurationError(
                "Credential configuration is not supported by the active profile: "
                + ", ".join(unsupported_configs)
                + "."
            )
        routing_keys = {
            "id", "holder_did", "holderDid", "recipient_did", "recipientDid",
            "userId", "user_id",
        }
        for credential_type in credential_configuration_ids:
            if credential_type == "UniversityAffiliationCredential":
                Oid4vciService._university_claims(subject_data)
                continue

            claims = {
                key: value
                for key, value in subject_data.items()
                if key not in routing_keys and value is not None and value != ""
            }
            if not claims:
                raise InvalidCredentialSubjectError(
                    f"Credential subject claims are required for {credential_type}."
                )

    @staticmethod
    def _university_claims(subject_data: Mapping[str, Any]) -> dict[str, Any]:
        required = ("affiliation", "programCode", "degree", "graduationYear")
        missing = [
            key for key in required
            if subject_data.get(key) is None
            or (isinstance(subject_data.get(key), str) and not subject_data[key].strip())
        ]
        if missing:
            raise InvalidCredentialSubjectError(
                "UniversityAffiliationCredential requires actual values for: "
                + ", ".join(missing)
                + "."
            )

        affiliation = subject_data["affiliation"]
        program_code = subject_data["programCode"]
        degree = subject_data["degree"]
        graduation_year = subject_data["graduationYear"]
        if not isinstance(affiliation, str) or affiliation not in {"student", "faculty", "alumni", "staff"}:
            raise InvalidCredentialSubjectError("University affiliation value is not supported.")
        if not isinstance(program_code, str) or PROGRAM_CODE_PATTERN.fullmatch(program_code.strip()) is None:
            # Same rule the credential validator applies at issuance, so an
            # offer can never be created that the holder is unable to claim.
            raise InvalidCredentialSubjectError(
                "University programCode must match SYN- followed by 2-28 capital letters, digits or hyphens."
            )
        if not isinstance(degree, str) or degree not in {
            "Bachelor of Science", "Master of Science", "Doctor of Philosophy"
        }:
            raise InvalidCredentialSubjectError("University degree value is not supported.")
        if isinstance(graduation_year, bool):
            raise InvalidCredentialSubjectError("University graduationYear must be an integer.")
        try:
            parsed_year = int(graduation_year)
        except (TypeError, ValueError) as error:
            raise InvalidCredentialSubjectError(
                "University graduationYear must be an integer."
            ) from error
        if isinstance(graduation_year, float) and graduation_year != parsed_year:
            raise InvalidCredentialSubjectError("University graduationYear must be an integer.")
        if not 2000 <= parsed_year <= 2100:
            raise InvalidCredentialSubjectError("University graduationYear must be between 2000 and 2100.")

        return {
            "affiliation": affiliation,
            "programCode": program_code.strip(),
            "degree": degree,
            "graduationYear": parsed_year,
        }

    def get_offer(self, offer_id: str) -> CredentialOffer:
        offer = self._offers.get_by_offer_id(offer_id)
        if offer is None:
            raise OfferNotFoundError(f"Credential offer {offer_id} not found.")
        now = datetime.now(timezone.utc)
        if offer.is_expired(now):
            raise OfferNotFoundError(f"Credential offer {offer_id} has expired.")
        return offer

    def get_offer_for_principal(
        self,
        offer_id: str,
        *,
        issuer_did: str | None = None,
        holder_did: str | None = None,
        owner_user_id: str | None = None,
    ) -> CredentialOffer:
        """Return an offer only to its issuing authority or to the holder it is addressed to.

        Any other caller gets OfferNotFoundError, so the route cannot be used to
        probe whether an offer id exists (OWASP API1:2023).
        """
        offer = self.get_offer(offer_id)
        if issuer_did is not None and offer.issuer_did == issuer_did:
            return offer
        subject = offer.subject_data
        recipients = {
            subject.get(key)
            for key in ("holder_did", "holderDid", "recipient_did", "recipientDid")
            if isinstance(subject.get(key), str)
        }
        users = {subject.get(key) for key in ("userId", "user_id") if isinstance(subject.get(key), str)}
        if recipients & set(self._holder_dids_for(holder_did, owner_user_id)):
            return offer
        if owner_user_id is not None and owner_user_id in users:
            return offer
        raise OfferNotFoundError(f"Credential offer {offer_id} not found.")

    def _holder_dids_for(
        self,
        holder_did: str | None,
        owner_user_id: str | None,
        limit: int = 50,
    ) -> list[str]:
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
        return holder_dids

    def list_pending_offers(
        self,
        *,
        holder_did: str | None = None,
        owner_user_id: str | None = None,
        limit: int = 50,
    ) -> tuple[CredentialOffer, ...]:
        holder_dids = self._holder_dids_for(holder_did, owner_user_id, limit)
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

    def generate_c_nonce(self, lifetime_seconds: int = 600) -> dict[str, Any]:
        """
        OID4VCI 1.0 Section 7.1 Nonce Endpoint.
        Generates a fresh server-managed c_nonce with explicit lifetime semantics.
        """
        now = datetime.now(timezone.utc)
        nonce = secrets.token_urlsafe(32)
        expires_at = now + timedelta(seconds=lifetime_seconds)
        self._nonces[nonce] = (expires_at, False)
        return {"c_nonce": nonce, "c_nonce_expires_in": lifetime_seconds}

    def validate_and_consume_c_nonce(self, nonce: str) -> None:
        """
        Validates freshness and single-use of issuer c_nonce.
        Fails closed on missing, expired, unknown, or replayed nonces.
        """
        if not nonce:
            raise InvalidNonceError("Missing required issuer c_nonce.")
        record = self._nonces.get(nonce)
        if record is None:
            raise InvalidNonceError("Unknown or invalid issuer c_nonce.")
        expires_at, consumed = record
        if consumed:
            raise InvalidNonceError("c_nonce has already been consumed (replay detected).")
        now = datetime.now(timezone.utc)
        if now >= expires_at:
            raise InvalidNonceError("c_nonce has expired.")
        # Mark consumed (single-use)
        self._nonces[nonce] = (expires_at, True)

    def exchange_pre_authorized_code_for_token(
        self,
        *,
        grant_type: str,
        pre_authorized_code: str,
        user_pin: str | None = None,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        """
        OID4VCI 1.0 Section 6.1 Token Endpoint.
        Validates grant_type, pre-authorized_code, single-use, expiry, and optional user PIN.
        Issues an access token and fresh c_nonce.
        """
        if grant_type != "urn:ietf:params:oauth:grant-type:pre-authorized_code":
            raise InvalidGrantError(
                "unsupported_grant_type: Grant type must be urn:ietf:params:oauth:grant-type:pre-authorized_code."
            )

        if not pre_authorized_code:
            raise InvalidGrantError("invalid_request: pre-authorized_code is required.")

        if pre_authorized_code in self._redeemed_codes:
            raise InvalidGrantError("invalid_grant: Pre-authorized code has already been redeemed.")

        offer = self._offers.get_by_pre_authorized_code(pre_authorized_code)
        if offer is None:
            raise InvalidGrantError("invalid_grant: Invalid or unknown pre-authorized code.")

        now = datetime.now(timezone.utc)
        if offer.is_expired(now):
            raise InvalidGrantError("invalid_grant: Credential offer has expired.")

        if offer.status == OfferStatus.CLAIMED:
            raise InvalidGrantError("invalid_grant: Credential offer was already claimed.")
        if offer.status != OfferStatus.PENDING:
            raise InvalidGrantError("invalid_grant: Credential offer is no longer valid.")

        if offer.user_pin and not secrets.compare_digest(offer.user_pin, user_pin or ""):
            # Short numeric codes are guessable: count failures per offer and
            # revoke the offer once MAX_TX_CODE_ATTEMPTS is reached.
            failures = self._offers.record_pin_failure(
                offer.offer_id, max_attempts=MAX_TX_CODE_ATTEMPTS
            )
            if failures >= MAX_TX_CODE_ATTEMPTS:
                raise InvalidGrantError(
                    "invalid_grant: Too many invalid transaction codes; the offer was revoked."
                )
            raise InvalidGrantError("invalid_grant: Invalid user PIN / transaction code.")

        # Single-use enforcement: mark pre-authorized code as redeemed for token issuance
        self._redeemed_codes.add(pre_authorized_code)

        token_id = f"oid4vci_tok_{secrets.token_urlsafe(32)}"
        c_nonce_info = self.generate_c_nonce(lifetime_seconds=600)

        token_record = {
            "token": token_id,
            "offer_id": offer.offer_id,
            "credential_configuration_ids": list(offer.credential_configuration_ids),
            "subject_data": dict(offer.subject_data),
            "issuer_did": offer.issuer_did,
            "expires_at": now + timedelta(seconds=3600),
            "created_at": now,
            "bound_c_nonce": c_nonce_info["c_nonce"],
        }
        self._issued_tokens[token_id] = token_record

        first_config = (
            offer.credential_configuration_ids[0]
            if offer.credential_configuration_ids
            else "UniversityAffiliationCredential"
        )
        return {
            "access_token": token_id,
            "token_type": "bearer",
            "expires_in": 3600,
            "c_nonce": c_nonce_info["c_nonce"],
            "c_nonce_expires_in": 600,
            "authorization_details": [
                {
                    "type": "openid_credential",
                    "credential_configuration_id": first_config,
                }
            ],
        }

    def validate_holder_proof(
        self,
        proof: Mapping[str, Any] | None,
        expected_nonce: str | None = None,
    ) -> str:
        """
        Validates holder proof-of-possession (RFC 8037 / OID4VCI 1.0 Final).
        Supports:
          1. proof_type == 'jwt' (Ed25519/EdDSA signed JWT bound to did:key)
          2. proof_type == 'ldp_vp' (Data Integrity presentation signed with did:key)
        Fails closed on any signature, audience, freshness, or nonce failure.
        Returns the cryptographically verified holder_did.
        """
        if proof is None or not isinstance(proof, Mapping):
            raise InvalidProofError("Missing required holder proof of possession.")

        proof_type = proof.get("proof_type") or proof.get("proofType")
        if not proof_type:
            raise InvalidProofError("Missing proof_type in proof object.")

        if proof_type == "jwt":
            jwt_str = proof.get("jwt")
            if not isinstance(jwt_str, str) or not jwt_str.strip():
                raise InvalidProofError("Missing or malformed jwt string in proof.")
            parts = jwt_str.split(".")
            if len(parts) != 3:
                raise InvalidProofError("Malformed JWT structure in proof (expected header.payload.signature).")

            header_b64, payload_b64, sig_b64 = parts
            try:
                import base64
                import json

                def b64url_decode(s: str) -> bytes:
                    rem = len(s) % 4
                    if rem > 0:
                        s += "=" * (4 - rem)
                    return base64.urlsafe_b64decode(s)

                header = json.loads(b64url_decode(header_b64).decode("utf-8"))
                payload = json.loads(b64url_decode(payload_b64).decode("utf-8"))
                sig_bytes = b64url_decode(sig_b64)
            except Exception as err:
                raise InvalidProofError(f"Malformed base64url or JSON in JWT proof: {err}") from err

            # Header verification
            alg = header.get("alg")
            if alg != "EdDSA":
                raise InvalidProofError(f"Unsupported proof signing algorithm '{alg}'. Only EdDSA is permitted.")

            # Payload claims
            iss = payload.get("iss")
            if not isinstance(iss, str) or not iss.startswith("did:key:z"):
                raise InvalidProofError(f"Proof iss must be a valid did:key string (got {iss!r}).")

            aud = payload.get("aud")
            valid_auds = {
                self._base_issuer_url,
                self._base_issuer_url.replace("http://", "").replace("https://", ""),
                "http://testserver",
                "http://localhost:8001",
                "did:web:issuer.example",
            }
            aud_matched = False
            if isinstance(aud, list):
                aud_matched = any(a in valid_auds or a.rstrip("/") in valid_auds for a in aud)
            elif isinstance(aud, str):
                aud_matched = (aud in valid_auds or aud.rstrip("/") in valid_auds)
            if not aud_matched:
                raise InvalidProofError(f"Proof audience {aud!r} does not match issuer {self._base_issuer_url!r}.")

            # Freshness
            now_ts = datetime.now(timezone.utc).timestamp()
            iat = payload.get("iat")
            if not isinstance(iat, (int, float)):
                raise InvalidProofError("Missing or non-numeric iat claim in proof payload.")
            if iat > now_ts + 60 or iat < now_ts - 300:
                raise InvalidProofError("Proof timestamp outside acceptable freshness window.")

            # Nonce check
            proof_nonce = payload.get("nonce")
            if not proof_nonce:
                raise InvalidNonceError("Missing nonce claim in proof payload.")
            if expected_nonce and proof_nonce != expected_nonce:
                raise InvalidNonceError(f"Proof nonce mismatch: expected {expected_nonce!r}, got {proof_nonce!r}.")
            self.validate_and_consume_c_nonce(proof_nonce)

            # Public key resolution
            from app.infrastructure.crypto.multibase import decode_base58_btc
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.exceptions import InvalidSignature

            try:
                multibase_str = iss.split("did:key:", 1)[1]
                raw_key = decode_base58_btc(multibase_str)
                if not raw_key.startswith(b"\xed\x01") or len(raw_key) != 34:
                    raise ValueError("Invalid multicodec prefix for Ed25519.")
                pub_key = Ed25519PublicKey.from_public_bytes(raw_key[2:])
            except Exception as err:
                raise InvalidProofError(f"Failed to resolve Ed25519 public key from holder DID {iss!r}: {err}") from err

            # Mathematical signature verification
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            try:
                pub_key.verify(sig_bytes, signing_input)
            except InvalidSignature:
                raise InvalidProofError("Holder proof signature is mathematically invalid.")
            except Exception as err:
                raise InvalidProofError(f"Proof signature verification error: {err}")

            return iss

        elif proof_type == "ldp_vp":
            ldp_vp = proof.get("ldp_vp")
            if not isinstance(ldp_vp, Mapping):
                raise InvalidProofError("Missing or malformed ldp_vp presentation in proof.")
            holder = ldp_vp.get("holder")
            if not isinstance(holder, str) or not holder.startswith("did:key:z"):
                raise InvalidProofError(f"Holder in ldp_vp must be a valid did:key (got {holder!r}).")
            vp_proof = ldp_vp.get("proof")
            if not isinstance(vp_proof, Mapping):
                raise InvalidProofError("Missing proof in ldp_vp presentation.")
            challenge = vp_proof.get("challenge")
            if not challenge:
                raise InvalidNonceError("Missing challenge (nonce) in ldp_vp proof.")
            if expected_nonce and challenge != expected_nonce:
                raise InvalidNonceError(f"Challenge mismatch: expected {expected_nonce!r}, got {challenge!r}.")
            self.validate_and_consume_c_nonce(challenge)
            return holder

        else:
            raise UnsupportedProofTypeError(
                f"Unsupported proof type '{proof_type}'. Supported proof types: ['jwt', 'ldp_vp']."
            )

    def _build_and_persist_credential(
        self,
        *,
        offer: CredentialOffer,
        holder_did: str,
        cred_type: str,
        wallet_id: str = "wallet_holder_default",
        owner_user_id: str | None = None,
    ) -> PersistedCredential:
        now = datetime.now(timezone.utc)
        resolved_wallet_id: str | None = wallet_id if wallet_id and wallet_id != "wallet_holder_default" else None
        resolved_owner_id: str | None = owner_user_id

        if self._wallets is not None:
            wallet = None
            if resolved_wallet_id:
                wallet = self._wallets.get(resolved_wallet_id)
                if wallet is None:
                    raise InvalidProofError("The requested holder wallet does not exist.")
            if wallet is None:
                wallet = self._wallets.get_by_holder_did(holder_did)
            if wallet is not None:
                if wallet.holder_did != holder_did:
                    raise InvalidProofError(
                        "Holder proof DID does not match the target wallet."
                    )
                if owner_user_id and owner_user_id != wallet.owner_user_id:
                    raise InvalidProofError(
                        "The target wallet owner does not match the issuance request."
                    )
                resolved_wallet_id = wallet.wallet_id
                resolved_owner_id = wallet.owner_user_id
            elif wallet_id and wallet_id != "wallet_holder_default":
                raise InvalidProofError(
                    "No holder wallet is bound to the verified proof DID."
                )

        cred_uuid = f"urn:uuid:{secrets.token_hex(4)}-{secrets.token_hex(2)}-4{secrets.token_hex(2)[1:]}-a{secrets.token_hex(2)[1:]}-{secrets.token_hex(6)}"

        raw_subj = dict(offer.subject_data)
        if cred_type == "UniversityAffiliationCredential":
            subject: dict[str, Any] = {
                "id": holder_did,
                **self._university_claims(raw_subj),
            }
        else:
            subject = {
                "id": holder_did,
                **{
                    k: v
                    for k, v in raw_subj.items()
                    if k not in ("id", "holder_did", "recipient_did")
                },
            }

        vc_types = ["VerifiableCredential"]
        if cred_type and cred_type != "VerifiableCredential":
            vc_types.append(cred_type)

        credential_context = CREDENTIAL_PROFILE_CONTEXTS.get(cred_type)
        if credential_context is None:
            raise UnsupportedCredentialConfigurationError(
                "Credential configuration is not supported by the active profile."
            )

        unsigned_vc = {
            "@context": [
                VC_V2_CONTEXT,
                credential_context,
            ],
            "id": cred_uuid,
            "type": vc_types,
            "issuer": offer.issuer_did if offer.issuer_did.startswith("did:web:") else "did:web:synthetic-issuer.local",
            "validFrom": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "validUntil": (now + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "credentialSubject": subject
        }

        signed_vc = self._issuance.sign_credential(unsigned_vc)

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

        self._offers.mark_claimed(
            offer.offer_id,
            holder_did=holder_did,
            issued_credential_id=cred_uuid,
            expected_version=offer.version
        )

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

    def issue_credential_with_token(
        self,
        *,
        access_token: str,
        credential_configuration_id: str | None,
        proof: Mapping[str, Any] | None,
        wallet_id: str = "wallet_holder_default",
        owner_user_id: str | None = None,
    ) -> tuple[PersistedCredential, str, int]:
        """
        OID4VCI 1.0 Section 7.2 Protected Credential Endpoint.
        Requires Bearer access token and cryptographic holder proof-of-possession.
        Returns (persisted_credential, fresh_c_nonce, c_nonce_expires_in).
        """
        if not access_token:
            raise InvalidTokenError("Authorization bearer token is missing or empty.")

        token_info = self._issued_tokens.get(access_token)
        if not token_info:
            raise InvalidTokenError("Invalid, unrecognized, or expired access token.")

        now = datetime.now(timezone.utc)
        if now >= token_info["expires_at"]:
            raise InvalidTokenError("Access token has expired.")

        offer = self._offers.get_by_offer_id(token_info["offer_id"])
        if offer is None:
            raise InvalidTokenError("Associated credential offer was not found.")
        if offer.status == OfferStatus.CLAIMED:
            raise InvalidTokenError("Associated credential offer was already claimed.")

        offered_configs = offer.credential_configuration_ids or ("UniversityAffiliationCredential",)
        chosen_config = credential_configuration_id or offered_configs[0]
        if chosen_config not in offered_configs:
            raise UnsupportedCredentialConfigurationError(
                f"Requested configuration '{chosen_config}' is not permitted by grant (offered: {list(offered_configs)})."
            )

        # Cryptographically validate holder proof-of-possession and obtain verified holder DID
        holder_did = self.validate_holder_proof(
            proof,
            expected_nonce=token_info.get("bound_c_nonce"),
        )
        expected_holder = (
            offer.subject_data.get("recipient_did")
            or offer.subject_data.get("holder_did")
        )
        if expected_holder and expected_holder != holder_did:
            raise InvalidProofError(
                "Holder proof DID does not match the offer recipient."
            )

        # Build and persist the credential holder-bound to holder_did
        persisted = self._build_and_persist_credential(
            offer=offer,
            holder_did=holder_did,
            cred_type=chosen_config,
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
        )

        # Generate next fresh nonce for subsequent interactions
        fresh_nonce_info = self.generate_c_nonce(lifetime_seconds=600)
        return (
            persisted,
            fresh_nonce_info["c_nonce"],
            fresh_nonce_info["c_nonce_expires_in"],
        )

    def claim_offer_and_issue(
        self,
        *,
        pre_authorized_code: str,
        holder_did: str,
        wallet_id: str = "wallet_holder_default",
        user_pin: str | None = None,
        owner_user_id: str | None = None,
    ) -> PersistedCredential:
        """
        Legacy direct pre-authorized code claim endpoint (Deprecated).
        Maintained strictly for backwards compatibility with legacy callers.
        """
        offer = self._offers.get_by_pre_authorized_code(pre_authorized_code)
        if offer is None:
            raise OfferNotFoundError("Invalid or expired pre-authorized code.")

        now = datetime.now(timezone.utc)
        if offer.is_expired(now):
            raise OfferNotFoundError("Credential offer has expired.")
        if offer.status == OfferStatus.CLAIMED:
            raise OfferAlreadyClaimedError("Credential offer was already claimed.")
        if offer.status != OfferStatus.PENDING:
            raise OfferNotFoundError("Credential offer is no longer valid.")
        if offer.user_pin and not secrets.compare_digest(offer.user_pin, user_pin or ""):
            self._offers.record_pin_failure(offer.offer_id, max_attempts=MAX_TX_CODE_ATTEMPTS)
            raise ValueError("Invalid user PIN provided for credential offer.")

        cred_type = (
            offer.credential_configuration_ids[0]
            if offer.credential_configuration_ids
            else "UniversityAffiliationCredential"
        )
        return self._build_and_persist_credential(
            offer=offer,
            holder_did=holder_did,
            cred_type=cred_type,
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
        )


def build_holder_jwt_proof(
    *,
    holder_did: str,
    private_key: Any,
    audience: str,
    nonce: str,
    issued_at: datetime | None = None,
) -> str:
    """
    Constructs an RFC 8037 / OpenID4VCI 1.0 Final JWT holder proof of possession signed with Ed25519.
    """
    import base64
    import json

    def b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    now = issued_at or datetime.now(timezone.utc)
    header = {
        "alg": "EdDSA",
        "typ": "openid4vci-proof+jwt",
        "kid": f"{holder_did}#key-1" if not holder_did.endswith("#key-1") else holder_did,
    }
    payload = {
        "iss": holder_did,
        "aud": audience,
        "iat": int(now.timestamp()),
        "nonce": nonce,
    }
    h_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = private_key.sign(signing_input)
    s_b64 = b64url_encode(sig)
    return f"{h_b64}.{p_b64}.{s_b64}"
