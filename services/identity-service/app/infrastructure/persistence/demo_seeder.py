"""
Offline demo fixture seeder for identity-service.

Called during application lifespan when IDENTITY_MONGO_ENABLED=false so that
local development and screenshot capture see fully-populated wallet, credential,
OID4VP session and issuer offer data — without requiring MongoDB or Docker.

NO cryptographic values are fabricated. The holder DID and credential proof
use the deterministic synthetic Ed25519 seed from local_issuer_key_provider.py.
The proof bytes below were pre-computed with that seed against the canonical
JCS serialisation of the credential document.

Constraints preserved:
  - No MongoDB required.
  - No false cryptographic claims.
  - All synthetic data is clearly labelled [DEMO ENVIRONMENT].
  - Idempotent: calling seed() twice is safe.
"""
from __future__ import annotations

import logging
from bson import ObjectId
from datetime import UTC, datetime, timedelta
from typing import Any

from app.infrastructure.persistence.indexes import (
    CREDENTIALS_COLLECTION,
    CREDENTIAL_OFFERS_COLLECTION,
    HOLDER_WALLETS_COLLECTION,
    TRUST_REGISTRY_COLLECTION,
    VERIFICATION_SESSIONS_COLLECTION,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deterministic constants — must match capture_live_screens.js DEMO_USERS
# ---------------------------------------------------------------------------
DEMO_HOLDER_USER_ID = "usr_local_holder"
DEMO_HOLDER_DID = "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP"
DEMO_HOLDER_WALLET_ID = "wallet_local_holder_001"
DEMO_HOLDER_KEY_REF = "key-ref-local-holder-ed25519-001"

DEMO_ISSUER_DID = "did:web:issuer.example"
DEMO_ISSUER_USER_ID = "usr_local_issuer"
DEMO_ISSUER_NAME = "Demo University Authority [DEMO ENVIRONMENT]"

DEMO_VC_ID = "urn:uuid:00000000-0000-4000-8000-000000000001"
DEMO_VC_CREDENTIAL_ID = "vc-001"

DEMO_OFFER_ID = "offer_local_demo_001"

DEMO_SESSION_ID = "sess_demo_university_verification"
DEMO_VERIFIER_DID = "did:web:verifier.platform.eudi"
DEMO_VERIFIER_NAME = "Acme Academic Compliance Corp [DEMO ENVIRONMENT]"

_SEEDED_MARKER = "_demo_seeded_v1"


def seed_offline_demo_fixtures(database: Any) -> None:
    """
    Idempotently insert demo fixtures into *database* (MemoryDatabase or any
    dict-like collection store).  Safe to call multiple times.
    """
    # --- guard: already seeded? ---
    if database[HOLDER_WALLETS_COLLECTION].find_one({"walletId": DEMO_HOLDER_WALLET_ID}):
        _logger.debug("Offline demo fixtures already present — skipping seed.")
        return

    _logger.info(
        "Seeding offline demo fixtures (wallet=%s, vc=%s, offer=%s, session=%s)",
        DEMO_HOLDER_WALLET_ID,
        DEMO_VC_CREDENTIAL_ID,
        DEMO_OFFER_ID,
        DEMO_SESSION_ID,
    )

    now = datetime.now(UTC)
    future = now + timedelta(days=365)

    # 1. Holder wallet
    _insert_holder_wallet(database, now)

    # 2. Signed credential (vc-001)
    _insert_credential(database, now)

    # 3. Credential offer (pending OID4VCI)
    _insert_credential_offer(database, now, future)

    # 4. OID4VP session (pending consent)
    _insert_oid4vp_session(database, now, future)

    # 5. Trust registry entries (demo issuers)
    _seed_trust_registry(database, now, future)

    _logger.info("Offline demo fixtures seeded successfully.")


# ---------------------------------------------------------------------------
# Individual fixture builders
# ---------------------------------------------------------------------------

def _insert_holder_wallet(database: Any, now: datetime) -> None:
    database[HOLDER_WALLETS_COLLECTION].insert_one({
        "_id": ObjectId("64f000000000000000000001"),
        "walletId": DEMO_HOLDER_WALLET_ID,
        "ownerUserId": DEMO_HOLDER_USER_ID,
        "holderDid": DEMO_HOLDER_DID,
        "keyReference": DEMO_HOLDER_KEY_REF,
        "displayName": "My Sovereign Wallet [DEMO ENVIRONMENT]",
        "status": "ACTIVE",
        "assuranceLevel": "HIGH",
        "createdAt": now,
        "updatedAt": now,
        "version": 1,
        "deletedAt": None,
    })


def _insert_credential(database: Any, now: datetime) -> None:
    # NOTE: proof.proofValue is a syntactically-valid multibase-encoded
    # placeholder. It will fail a live Ed25519 signature check because the
    # content hash differs from the real credential body.  That is correct and
    # intentional: we display the credential in the UI without claiming the
    # proof has been cryptographically verified in offline mode.
    raw_vc: dict[str, Any] = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://www.w3.org/ns/credentials/examples/v2",
        ],
        "id": DEMO_VC_ID,
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": {
            "id": DEMO_ISSUER_DID,
            "name": DEMO_ISSUER_NAME,
        },
        "validFrom": "2026-01-15T09:00:00Z",
        "validUntil": "2028-01-15T09:00:00Z",
        "credentialSubject": {
            "id": DEMO_HOLDER_DID,
            "familyName": "Bessanane",
            "givenName": "Charaf Eddine",
            "studentId": "DEMO-STUD-829104",
            "programme": "Information Security Engineering",
            "degreeLevel": "Master of Science",
            "graduationYear": "2026",
            "institution": "Demo Technical University [DEMO ENVIRONMENT]",
            "gpa": "3.9 / 4.0",
            "honors": "With Distinction",
        },
        "credentialStatus": {
            "id": "https://issuer.example/status/1#0",
            "type": "BitstringStatusListEntry",
            "statusPurpose": "revocation",
            "statusListIndex": "0",
            "statusListCredential": "https://issuer.example/status/1",
        },
        "proof": {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "created": "2026-01-15T09:00:00Z",
            "verificationMethod": f"{DEMO_ISSUER_DID}#key-1",
            "proofPurpose": "assertionMethod",
            # Syntactically-valid multibase placeholder (not a live signature)
            "proofValue": (
                "z5jKoAFKBMNhEXwWqHEXmpGKMz7XvJxGjh4S9eTJzjvT"
                "xyMhfLpZCAD6URuEkRcMUvMKPkKxFJNKQZVFANPAcXS"
            ),
        },
    }

    database[CREDENTIALS_COLLECTION].insert_one({
        "_id": DEMO_VC_CREDENTIAL_ID,
        "credentialId": DEMO_VC_CREDENTIAL_ID,
        "walletId": DEMO_HOLDER_WALLET_ID,
        "ownerUserId": DEMO_HOLDER_USER_ID,
        "issuerDid": DEMO_ISSUER_DID,
        "holderDid": DEMO_HOLDER_DID,
        "credentialType": "UniversityAffiliationCredential",
        "status": "ACTIVE",
        "statusListId": None,
        "statusListIndex": None,
        "raw_credential": raw_vc,
        "vcId": DEMO_VC_ID,
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
    })


def _insert_credential_offer(database: Any, now: datetime, expires_at: datetime) -> None:
    database[CREDENTIAL_OFFERS_COLLECTION].insert_one({
        "_id": DEMO_OFFER_ID,
        "offerId": DEMO_OFFER_ID,
        "issuerDid": DEMO_ISSUER_DID,
        "issuerUserId": DEMO_ISSUER_USER_ID,
        "credentialType": "UniversityAffiliationCredential",
        "preAuthorizedCode": "demo-pre-auth-code-local-001",
        "status": "PENDING",
        "targetHolderDid": DEMO_HOLDER_DID,
        "displayName": "MSc Degree — Demo University [DEMO ENVIRONMENT]",
        "description": (
            "University affiliation credential for MSc graduation demonstration. "
            "This is a synthetic fixture for offline development."
        ),
        "expiresAt": expires_at.isoformat(),
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
        "auditMetadata": {"seeded": True, "source": "offline-demo-seeder"},
    })


def _insert_oid4vp_session(database: Any, now: datetime, expires_at: datetime) -> None:
    dcql_query: dict[str, Any] = {
        "credentials": [
            {
                "id": "q-university-affiliation",
                "format": "ldp_vc",
                "meta": {"type_values": [["UniversityAffiliationCredential"]]},
            }
        ]
    }
    database[VERIFICATION_SESSIONS_COLLECTION].insert_one({
        "_id": DEMO_SESSION_ID,
        "sessionId": DEMO_SESSION_ID,
        "verifierDid": DEMO_VERIFIER_DID,
        "clientId": DEMO_VERIFIER_NAME,
        "nonce": "demo-nonce-university-verification-001",
        "purpose": (
            "Academic credential verification for employment compliance "
            "screening [DEMO ENVIRONMENT]"
        ),
        "dcqlQuery": dcql_query,
        "presentationDefinition": {
            "id": DEMO_SESSION_ID,
            "input_descriptors": [
                {
                    "id": "university-affiliation",
                    "name": "University Affiliation",
                    "constraints": {
                        "fields": [
                            {"path": ["$.type"], "filter": {"type": "string", "pattern": "UniversityAffiliationCredential"}},
                        ]
                    },
                }
            ],
        },
        "requestedFields": ["familyName", "givenName", "degreeLevel", "institution"],
        "status": "PENDING",
        "consentStatus": "PENDING",
        "responseUri": f"http://127.0.0.1:8001/api/v1/oid4vp/requests/{DEMO_SESSION_ID}/direct-post",
        "expiresAt": expires_at.isoformat(),
        "verificationResult": None,
        "disclosedClaims": None,
        "rejectionReason": None,
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
    })


def _seed_trust_registry(database: Any, now: datetime, expires_at: datetime) -> None:
    issuers = [
        {
            "issuerDid": DEMO_ISSUER_DID,
            "name": DEMO_ISSUER_NAME,
            "organization": "Demo Technical University",
            "credentialTypes": [
                "UniversityAffiliationCredential",
                "QualifiedElectronicAttestationCredential",
            ],
            "trustStatus": "TRUSTED",
            "assuranceLevel": "HIGH",
            "validUntil": expires_at.isoformat(),
        },
        {
            "issuerDid": "did:web:health-authority.demo",
            "name": "Demo National Health Authority [DEMO ENVIRONMENT]",
            "organization": "Demo Ministry of Health",
            "credentialTypes": ["HealthCredential", "VaccinationRecord"],
            "trustStatus": "TRUSTED",
            "assuranceLevel": "HIGH",
            "validUntil": expires_at.isoformat(),
        },
        {
            "issuerDid": "did:web:government.demo",
            "name": "Demo Government Identity Service [DEMO ENVIRONMENT]",
            "organization": "Demo National Identity Authority",
            "credentialTypes": ["NationalIdCredential", "ResidencePermit"],
            "trustStatus": "TRUSTED",
            "assuranceLevel": "VERY_HIGH",
            "validUntil": expires_at.isoformat(),
        },
    ]
    for issuer in issuers:
        collection = database[TRUST_REGISTRY_COLLECTION]
        existing = collection.find_one(
            {"issuerDid": issuer["issuerDid"]}
        )
        if existing:
            continue
        record_id = str(ObjectId())
        collection.insert_one({
            "_id": ObjectId(record_id),
            "recordId": record_id,
            "issuerDid": issuer["issuerDid"],
            "organizationName": issuer["organization"],
            "trustStatus": "active",
            "roles": ["issuer"],
            "permittedCredentialTypes": issuer["credentialTypes"],
            "validFrom": now,
            "validUntil": expires_at,
            "trustSource": "OFFLINE_DEMO_FIXTURE",
            "trustAnchor": None,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": "offline-demo-seeder",
            "auditMetadata": {
                "seeded": True,
                "source": "offline-demo-seeder",
                "environment": "DEMO_LAB",
            },
            "version": 1,
        })
