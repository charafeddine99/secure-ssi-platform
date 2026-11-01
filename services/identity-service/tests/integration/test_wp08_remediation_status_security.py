"""WP-08 Remediation Integration Tests — Status & Trust Policy Integration (R1, R2, R3).

Explicitly validates:
- R1 (HIGH): Status service exceptions fail closed (never VERIFIED/ACTIVE).
- R2 (MEDIUM): Suspension status enforcement (active suspension bit -> REJECTED;
  distinguishes suspended from revoked; rejects unsupported statusPurpose).
- R3 (MEDIUM): Status-list credential proof validation (DataIntegrityProof over JCS canonical input;
  tampered encodedList, tampered proof, wrong issuer, missing proof all fail closed).
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1 import dependencies
from app.application.services.oid4vp_service import fraud_client
from app.infrastructure import cache_and_anchor
from app.api.v1.dependencies import (
    get_status_list_service,
    get_credential_repository,
    get_trust_registry_service,
)
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
    build_signed_presentation,
)
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalHolderKeyProvider,
    SYNTHETIC_HOLDER_DID,
)
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.crypto.ed25519_signer import Ed25519CredentialSigner
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.status_list_document_generator import (
    StatusListDocumentGenerator,
    encode_status_list,
)
from app.infrastructure.crypto.multibase import encode_base58_btc
from app.domain.bitstring_status_list import StatusListPublication, StatusPurpose
from app.domain.credential_status import CredentialStatus
from app.domain.did import DidResolutionMetadata, DidResolutionResult
from app.domain.oid4vp import ConsentAction, ConsentDecision
from app.services.did_document_validator import (
    DID_V1_CONTEXT,
    MULTIKEY_V1_CONTEXT,
    DidDocumentValidator,
)
from app.services.did_resolver import CompositeDidResolver

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_optional_fraud_dependency(monkeypatch: pytest.MonkeyPatch):
    # Status/trust tests exercise their own policy dependencies. Avoid making
    # them depend on or mutate a separately running Fraud Service instance.
    monkeypatch.setattr(fraud_client, "base_url", "http://127.0.0.1:1")
    monkeypatch.setattr(fraud_client, "report_event", lambda **kwargs: None)

PASSWORDS = {
    "verifier": "Verifier-Prototype-2026!",
}


def _verifier_headers() -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": "verifier@example.test", "password": PASSWORDS["verifier"]},
    )
    assert res.status_code == 200, f"Auth failed: {res.text}"
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def _create_session(headers: dict[str, str]) -> dict[str, Any]:
    res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "WP-08 Remediation Test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree", "programCode"],
            "ttlSeconds": 300,
        },
        headers=headers,
    )
    assert res.status_code == 201, f"Session create failed: {res.text}"
    return res.json()


def _record_test_consent(
    session: dict[str, Any], vp_token: dict[str, Any]
) -> None:
    """Record the explicit Holder decision required by the local OID4VP profile."""
    manager = dependencies.get_mongo_connection_manager()
    sessions = dependencies.get_verification_session_repository(manager=manager)
    stored = sessions.get_by_session_id(session["sessionId"])
    assert stored is not None
    credential = vp_token["verifiableCredential"][0]
    subject = credential["credentialSubject"]
    sessions.record_consent(
        stored.session_id,
        consent_decision=ConsentDecision(
            session_id=stored.session_id,
            verifier_did=stored.verifier_did,
            client_id=stored.client_id,
            purpose=stored.purpose,
            nonce=stored.nonce,
            holder_did=vp_token["holder"],
            decision=ConsentAction.APPROVE,
            approved_credentials=(credential["id"],),
            requested_claims=stored.requested_fields,
            approved_claims={key: value for key, value in subject.items() if key != "id"},
            expires_at=stored.expires_at,
        ),
        expected_version=stored.version,
    )


def _make_vc_with_status(
    *,
    nonce: str,
    status_purpose: str = "revocation",
    status_list_index: int = 0,
    status_list_url: str = "http://localhost:8001/api/v1/status-lists/revocation-000000000000000000000001",
    include_status: bool = True,
    status_entries: list[dict[str, Any]] | None = None,
    allow_invalid_status: bool = False,
    vc_id: str = "urn:uuid:98765432-1234-4567-89ab-000000000001",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    unsigned_vc: dict[str, Any] = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": vc_id,
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": SYNTHETIC_ISSUER_DID,
        "validFrom": (now - timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": SYNTHETIC_HOLDER_DID,
            "affiliation": "student",
            "programCode": "SYN-CS-001",
            "degree": "Bachelor of Science",
            "graduationYear": 2026,
        },
    }
    if include_status:
        unsigned_vc["credentialStatus"] = (
            status_entries
            if status_entries is not None
            else {
                "id": "urn:uuid:00000000-0000-4000-8000-000000000001",
                "type": "BitstringStatusListEntry",
                "statusPurpose": status_purpose,
                "statusListIndex": str(status_list_index),
                "statusListCredential": status_list_url,
            }
        )

    proof_service = build_local_proof_service(clock=lambda: now)
    if allow_invalid_status:
        # These API regressions need a correctly signed VC carrying an
        # intentionally malformed status value. Bypass only status-profile
        # validation while creating the test credential; production
        # verification remains unchanged and rejects malformed entries.
        with patch.object(
            proof_service.validator,
            "_validate_credential_status",
            return_value=None,
        ):
            signed_vc = proof_service.sign_credential(unsigned_vc)
    else:
        signed_vc = proof_service.sign_credential(unsigned_vc)
    return build_signed_presentation(
        signed_vc,
        nonce=nonce,
        domain="http://testserver/verifier",
        holder_did=SYNTHETIC_HOLDER_DID,
    )


def _generate_status_list_publication(
    *,
    status_list_id: str = "revocation-000000000000000000000001",
    issuer_did: str = SYNTHETIC_ISSUER_DID,
    status_purpose: str = "revocation",
    active_indices: list[int] | None = None,
    encoded_list_length: int = 131072,
) -> StatusListPublication:
    now = datetime.now(timezone.utc)
    generator = StatusListDocumentGenerator(
        canonicalizer=JcsCanonicalizer(),
        signer=Ed25519CredentialSigner(),
        key_provider=LocalIssuerKeyProvider(),
    )
    encoded = encode_status_list(
        active_indices or [],
        list_length=encoded_list_length,
    )
    url = f"http://localhost:8001/api/v1/status-lists/{status_list_id}"
    doc = generator.generate(
        status_list_url=url,
        issuer_did=issuer_did,
        encoded_list=encoded,
        ttl_seconds=3600,
        published_at=now,
        status_purpose=status_purpose,
    )
    content_hash = hashlib.sha256(encoded.encode()).hexdigest()
    return StatusListPublication(
        id="000000000000000000000001",
        status_list_id=status_list_id,
        issuer_did=issuer_did,
        status_purpose=StatusPurpose(status_purpose),
        encoded_list=encoded,
        content_hash=content_hash,
        document=doc,
        list_length=131072,
        capacity=131072,
        assigned_entries=1,
        revoked_entries=len(active_indices or []),
        ttl_seconds=3600,
        etag=f'"{content_hash}-v1"',
        published_at=now,
        created_at=now,
        updated_at=now,
    )


def _publication_with_document(
    publication: StatusListPublication,
    document: dict[str, Any],
) -> StatusListPublication:
    return replace(publication, document=document)


def _resign_status_list_document(
    document: dict[str, Any],
    *,
    issuer_did: str,
    signing_key: Any,
    verification_method: str,
) -> dict[str, Any]:
    unsigned = copy.deepcopy(document)
    proof = dict(unsigned.pop("proof"))
    proof.pop("proofValue", None)
    unsigned["issuer"] = issuer_did
    proof["verificationMethod"] = verification_method
    signing_input = JcsCanonicalizer().create_signing_input(unsigned, proof)
    proof["proofValue"] = encode_base58_btc(signing_key.sign(signing_input))
    unsigned["proof"] = proof
    return unsigned


def _install_status_issuer_fixture_resolver(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dependencies: Any,
    issuer_did: str,
    verification_method: str,
    public_key_multibase: str,
) -> None:
    previous_resolver = dependencies._DID_RESOLVER
    document = {
        "@context": [DID_V1_CONTEXT, MULTIKEY_V1_CONTEXT],
        "id": issuer_did,
        "verificationMethod": [
            {
                "id": verification_method,
                "type": "Multikey",
                "controller": issuer_did,
                "publicKeyMultibase": public_key_multibase,
            }
        ],
        "assertionMethod": [verification_method],
    }

    class _StatusIssuerFixtureResolver:
        method = "web"

        def resolve(self, did: str) -> DidResolutionResult:
            if did != issuer_did:
                return previous_resolver.resolve(did)
            validated = DidDocumentValidator().validate(
                document,
                expected_did=issuer_did,
            )
            return DidResolutionResult(
                did=issuer_did,
                did_document=validated,
                metadata=DidResolutionMetadata(
                    method="web",
                    source="local-test-fixture",
                ),
            )

    monkeypatch.setattr(
        dependencies,
        "_DID_RESOLVER",
        CompositeDidResolver({"web": _StatusIssuerFixtureResolver()}),
    )


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


class TestWp08R1StatusServiceFailClosed:
    """R1 — HIGH: Status service exceptions must fail closed."""

    def test_status_service_exception_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"])

        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.side_effect = RuntimeError("Database connection timed out during status lookup")
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Status service resolution failed" in result["details"]["evaluations"]["revocation"]

    def test_status_service_unconfigured_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"])

        app.dependency_overrides[get_status_list_service] = lambda: None

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Status list service unavailable" in result["details"]["evaluations"]["revocation"]

    def test_missing_status_publication_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"])

        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.return_value = None
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Status list credential document missing" in result["details"]["evaluations"]["revocation"]

    def test_status_service_timeout_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"])

        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.side_effect = TimeoutError(
            "Status publication lookup timed out"
        )
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Status service resolution failed: TimeoutError" in result["details"]["evaluations"]["revocation"]

    def test_persistence_lookup_exception_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        credential_id = "urn:uuid:11112222-3333-4444-5555-666677778880"
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            vc_id=credential_id,
            include_status=False,
        )
        repository = MagicMock()
        repository.get_by_credential_id.side_effect = TimeoutError(
            "persistence lookup timed out"
        )
        app.dependency_overrides[get_credential_repository] = lambda: repository

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Credential status persistence unavailable: TimeoutError" in result["details"]["evaluations"]["revocation"]

    def test_quarantine_lookup_exception_fails_closed(self, monkeypatch):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            include_status=False,
        )
        mock_anchor = SimpleNamespace(
            is_quarantined=MagicMock(
                side_effect=TimeoutError("quarantine lookup timed out")
            )
        )
        monkeypatch.setattr(cache_and_anchor, "blockchain_anchor", mock_anchor)

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Quarantine status unavailable" in result["details"]["evaluations"]["revocation"]
        assert result["details"]["evaluations"]["quarantine"].startswith("Unavailable:")

    def test_issuer_trust_registry_timeout_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            include_status=False,
        )
        mock_trust_registry = MagicMock()
        mock_trust_registry.evaluate_issuer_trust.side_effect = TimeoutError(
            "issuer trust registry timed out"
        )
        app.dependency_overrides[get_trust_registry_service] = (
            lambda: mock_trust_registry
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["issuerTrusted"] is False
        assert "TRUST_REGISTRY_UNAVAILABLE:TimeoutError" in result["details"]["trust"]["reason"]

    def test_issuer_trust_registry_malformed_result_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            include_status=False,
        )
        mock_trust_registry = MagicMock()
        mock_trust_registry.evaluate_issuer_trust.return_value = SimpleNamespace(
            is_trusted="true",
            status=None,
            reason=None,
            trust_source=None,
            trust_record_id=None,
        )
        app.dependency_overrides[get_trust_registry_service] = (
            lambda: mock_trust_registry
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["issuerTrusted"] is False
        assert result["details"]["trust"]["reason"] == "TRUST_REGISTRY_INVALID_RESULT"


class TestWp08R2SuspensionStatusEnforcement:
    """R2 — MEDIUM: Suspension status enforcement."""

    def test_empty_credential_status_array_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_entries=[],
            allow_invalid_status=True,
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "at least one status entry" in result["details"]["evaluations"]["revocation"]

    @pytest.mark.parametrize("entry_type", [None, "OtherStatusEntry"])
    def test_unsupported_credential_status_entry_type_fails_closed(self, entry_type):
        headers = _verifier_headers()
        session = _create_session(headers)
        entry = {
            "id": "urn:uuid:00000000-0000-4000-8000-000000000001",
            "type": entry_type,
            "statusPurpose": "revocation",
            "statusListIndex": "0",
            "statusListCredential": "http://localhost:8001/api/v1/status-lists/revocation-000000000000000000000001",
        }
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_entries=[entry],
            allow_invalid_status=True,
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "entry type is unsupported or missing" in result["details"]["evaluations"]["revocation"]

    def test_active_suspension_status_rejected(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_purpose="suspension",
            status_list_index=42,
            status_list_url="http://localhost:8001/api/v1/status-lists/suspension-000000000000000000000001",
        )
        _record_test_consent(session, vp_token)

        pub = _generate_status_list_publication(
            status_list_id="suspension-000000000000000000000001",
            status_purpose="suspension",
            active_indices=[42],  # index 42 is suspended
        )
        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.return_value = pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Credential suspended" in result["details"]["evaluations"]["revocation"]

    def test_inactive_suspension_status_accepted(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_purpose="suspension",
            status_list_index=42,
            status_list_url="http://localhost:8001/api/v1/status-lists/suspension-000000000000000000000001",
        )
        _record_test_consent(session, vp_token)

        pub = _generate_status_list_publication(
            status_list_id="suspension-000000000000000000000001",
            status_purpose="suspension",
            active_indices=[99],  # index 42 is NOT suspended
        )
        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.return_value = pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "ACCEPTED"
        assert result["revocationStatusClear"] is True

    def test_persisted_suspended_status_rejected(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        cred_id = "urn:uuid:11112222-3333-4444-5555-666677778888"
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            vc_id=cred_id,
            include_status=False,
        )

        mock_persisted = MagicMock()
        mock_persisted.status = CredentialStatus.SUSPENDED
        mock_cred_repo = MagicMock()
        mock_cred_repo.get_by_credential_id.return_value = mock_persisted
        app.dependency_overrides[get_credential_repository] = lambda: mock_cred_repo

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Credential suspended in persistence" in result["details"]["evaluations"]["revocation"]

    def test_active_revocation_status_rejected(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_purpose="revocation",
            status_list_index=42,
        )
        publication = _generate_status_list_publication(
            status_purpose="revocation",
            active_indices=[42],
        )
        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Credential revoked (status bit set)" in result["details"]["evaluations"]["revocation"]

    def test_persisted_revoked_status_rejected(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        credential_id = "urn:uuid:11112222-3333-4444-5555-666677778889"
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            vc_id=credential_id,
            include_status=False,
        )
        persisted = MagicMock()
        persisted.status = CredentialStatus.REVOKED
        credential_repository = MagicMock()
        credential_repository.get_by_credential_id.return_value = persisted
        app.dependency_overrides[get_credential_repository] = (
            lambda: credential_repository
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Credential revoked in persistence" in result["details"]["evaluations"]["revocation"]

    @pytest.mark.parametrize(
        ("field", "value", "expected_reason"),
        [
            (
                "statusPurpose",
                None,
                "Unsupported or malformed statusPurpose",
            ),
            ("statusListIndex", "not-an-index", "statusListIndex is invalid"),
        ],
    )
    def test_malformed_suspension_status_rejected(
        self,
        field,
        value,
        expected_reason,
    ):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_purpose="suspension",
            status_list_index=42,
        )
        vp_token["verifiableCredential"][0]["credentialStatus"][field] = value

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert expected_reason in result["details"]["evaluations"]["revocation"]

    def test_unsupported_status_purpose_rejected(self):
        headers = _verifier_headers()
        session = _create_session(headers)

        now = datetime.now(timezone.utc)
        raw_vc = {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "id": "urn:uuid:22223333-4444-5555-6666-777788889999",
            "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
            "issuer": SYNTHETIC_ISSUER_DID,
            "validFrom": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
            "credentialSubject": {
                "id": SYNTHETIC_HOLDER_DID,
                "degree": "MSc",
            },
            "credentialStatus": {
                "id": "urn:uuid:00000000-0000-4000-8000-000000000001",
                "type": "BitstringStatusListEntry",
                "statusPurpose": "unsupported_purpose_foo",
                "statusListIndex": "0",
                "statusListCredential": "http://localhost:8001/api/v1/status-lists/revocation-000000000000000000000001",
            },
        }
        vp_token = build_signed_presentation(
            raw_vc,
            nonce=session["nonce"],
            domain="http://testserver/verifier",
            holder_did=SYNTHETIC_HOLDER_DID,
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Unsupported or malformed statusPurpose" in result["details"]["evaluations"]["revocation"]

    def test_missing_status_purpose_rejected(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        entry = {
            "id": "urn:uuid:00000000-0000-4000-8000-000000000001",
            "type": "BitstringStatusListEntry",
            "statusListIndex": "0",
            "statusListCredential": "http://localhost:8001/api/v1/status-lists/revocation-000000000000000000000001",
        }
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_entries=[entry],
            allow_invalid_status=True,
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Unsupported or malformed statusPurpose" in result["details"]["evaluations"]["revocation"]


class TestWp08R3StatusListProofValidation:
    """R3 — MEDIUM: Status-list credential proof validation."""

    def test_valid_status_list_credential_proof_accepted(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )
        _record_test_consent(session, vp_token)

        pub = _generate_status_list_publication(active_indices=[])
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "ACCEPTED"
        assert result["revocationStatusClear"] is True

    def test_document_issuer_must_match_publication_metadata(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )
        publication = _generate_status_list_publication(active_indices=[])
        mismatched_publication = replace(
            publication,
            issuer_did="did:web:status-list-metadata-mismatch.example",
        )
        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.return_value = mismatched_publication
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_ISSUER_MISMATCH_WITH_PUBLICATION" in result["details"]["evaluations"]["revocation"]

    def test_status_list_url_must_match_publication_identifier(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_url="http://localhost:8001/api/v1/status-lists/revocation-000000000000000000000002",
        )
        publication = _generate_status_list_publication(active_indices=[])
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "publication identifier mismatch" in result["details"]["evaluations"]["revocation"]

    def test_status_list_credential_requires_bitstring_type(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"], status_list_index=10)
        _record_test_consent(session, vp_token)
        publication = _generate_status_list_publication(active_indices=[])
        document = copy.deepcopy(dict(publication.document))
        document["type"] = ["VerifiableCredential"]
        issuer_key = LocalIssuerKeyProvider().get_signing_key(SYNTHETIC_ISSUER_DID)
        document = _resign_status_list_document(
            document,
            issuer_did=SYNTHETIC_ISSUER_DID,
            signing_key=issuer_key,
            verification_method=issuer_key.verification_method,
        )
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = _publication_with_document(
            publication,
            document,
        )
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_CREDENTIAL_UNSUPPORTED_TYPE" in result["details"]["evaluations"]["revocation"]

    def test_trusted_distinct_status_list_issuer_is_accepted(self, monkeypatch):
        import app.api.v1.dependencies as dependencies

        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"], status_list_index=10)
        _record_test_consent(session, vp_token)
        publication = _generate_status_list_publication(active_indices=[])

        key_provider = LocalHolderKeyProvider()
        metadata = key_provider.provision("local-dev:wp08-status-list-issuer:v1")
        status_issuer = "did:web:status-list-issuer.example"
        verification_method = f"{status_issuer}#key-1"
        status_key = key_provider.get_signing_key(metadata.holder_did)
        public_key = key_provider.get_verification_key(
            metadata.verification_method
        )
        _install_status_issuer_fixture_resolver(
            monkeypatch,
            dependencies=dependencies,
            issuer_did=status_issuer,
            verification_method=verification_method,
            public_key_multibase=encode_base58_btc(
                b"\xed\x01" + public_key.public_key_bytes
            ),
        )
        document = _resign_status_list_document(
            copy.deepcopy(dict(publication.document)),
            issuer_did=status_issuer,
            signing_key=status_key,
            verification_method=verification_method,
        )
        publication = replace(
            publication,
            issuer_did=status_issuer,
            document=document,
        )
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )
        trusted = SimpleNamespace(
            is_trusted=True,
            status=SimpleNamespace(value="ACTIVE"),
            reason="ISSUER_TRUST_VALID",
            trust_source="TEST",
            trust_record_id="trusted-issuer-record",
        )
        trust_registry = MagicMock()
        trust_registry.evaluate_issuer_trust.return_value = trusted
        app.dependency_overrides[get_trust_registry_service] = (
            lambda: trust_registry
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "ACCEPTED"
        assert result["revocationStatusClear"] is True
        assert status_issuer != SYNTHETIC_ISSUER_DID
        assert trust_registry.evaluate_issuer_trust.call_count == 2
        assert {
            call.kwargs["issuer_did"]
            for call in trust_registry.evaluate_issuer_trust.call_args_list
        } == {SYNTHETIC_ISSUER_DID, status_issuer}

    def test_unauthorized_status_list_verification_method_fails_closed(
        self,
        monkeypatch,
    ):
        import app.api.v1.dependencies as dependencies

        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"], status_list_index=10)
        publication = _generate_status_list_publication(active_indices=[])

        key_provider = LocalHolderKeyProvider()
        metadata = key_provider.provision("local-dev:wp08-unauthorized-status:v1")
        status_key = key_provider.get_signing_key(metadata.holder_did)
        status_issuer = "did:web:unauthorized-status-issuer.example"
        authorized_method = f"{status_issuer}#key-1"
        unauthorized_method = f"{status_issuer}#unauthorized-key"
        public_key = key_provider.get_verification_key(
            metadata.verification_method
        )
        _install_status_issuer_fixture_resolver(
            monkeypatch,
            dependencies=dependencies,
            issuer_did=status_issuer,
            verification_method=authorized_method,
            public_key_multibase=encode_base58_btc(
                b"\xed\x01" + public_key.public_key_bytes
            ),
        )
        document = _resign_status_list_document(
            copy.deepcopy(dict(publication.document)),
            issuer_did=status_issuer,
            signing_key=status_key,
            verification_method=unauthorized_method,
        )
        publication = replace(
            publication,
            issuer_did=status_issuer,
            document=document,
        )
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )
        trust_registry = MagicMock()
        trust_registry.evaluate_issuer_trust.return_value = SimpleNamespace(
            is_trusted=True,
            status=SimpleNamespace(value="ACTIVE"),
            reason="ISSUER_TRUST_VALID",
            trust_source="TEST",
            trust_record_id="trusted-issuer-record",
        )
        app.dependency_overrides[get_trust_registry_service] = (
            lambda: trust_registry
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_PROOF_INVALID" in result["details"]["evaluations"]["revocation"]

    def test_signed_status_list_shorter_than_minimum_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"], status_list_index=0)
        publication = _generate_status_list_publication(
            active_indices=[],
            encoded_list_length=8,
        )
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_ENCODED_LIST_INVALID:ValueError" in result["details"]["evaluations"]["revocation"]

    def test_signed_status_list_without_multibase_prefix_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"], status_list_index=0)
        publication = _generate_status_list_publication(active_indices=[])
        document = copy.deepcopy(dict(publication.document))
        document["credentialSubject"]["encodedList"] = publication.encoded_list[1:]
        issuer_key = LocalIssuerKeyProvider().get_signing_key(SYNTHETIC_ISSUER_DID)
        document = _resign_status_list_document(
            document,
            issuer_did=SYNTHETIC_ISSUER_DID,
            signing_key=issuer_key,
            verification_method=issuer_key.verification_method,
        )
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = _publication_with_document(
            publication,
            document,
        )
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_ENCODED_LIST_INVALID:ValueError" in result["details"]["evaluations"]["revocation"]

    def test_future_status_list_valid_from_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(nonce=session["nonce"], status_list_index=0)
        publication = _generate_status_list_publication(active_indices=[])
        document = copy.deepcopy(dict(publication.document))
        document["validFrom"] = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat().replace("+00:00", "Z")
        issuer_key = LocalIssuerKeyProvider().get_signing_key(SYNTHETIC_ISSUER_DID)
        document = _resign_status_list_document(
            document,
            issuer_did=SYNTHETIC_ISSUER_DID,
            signing_key=issuer_key,
            verification_method=issuer_key.verification_method,
        )
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = _publication_with_document(
            publication,
            document,
        )
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_NOT_YET_VALID" in result["details"]["evaluations"]["revocation"]

    def test_tampered_encoded_list_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )

        pub = _generate_status_list_publication(active_indices=[])
        tampered_doc = copy.deepcopy(dict(pub.document))
        # Tamper the document's encodedList AFTER signing
        tampered_doc["credentialSubject"]["encodedList"] = "u" + "A" * 100

        content_hash = hashlib.sha256(b"tampered").hexdigest()
        tampered_pub = StatusListPublication(
            id=pub.id,
            status_list_id=pub.status_list_id,
            issuer_did=pub.issuer_did,
            status_purpose=pub.status_purpose,
            encoded_list=tampered_doc["credentialSubject"]["encodedList"],
            content_hash=content_hash,
            document=tampered_doc,
            list_length=pub.list_length,
            capacity=pub.capacity,
            assigned_entries=pub.assigned_entries,
            revoked_entries=pub.revoked_entries,
            ttl_seconds=pub.ttl_seconds,
            etag=f'"{content_hash}-v1"',
            published_at=pub.published_at,
            created_at=pub.created_at,
            updated_at=pub.updated_at,
        )
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = tampered_pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Status list proof validation failed" in result["details"]["evaluations"]["revocation"]

    def test_tampered_proof_value_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )

        pub = _generate_status_list_publication(active_indices=[])
        tampered_doc = copy.deepcopy(dict(pub.document))
        original_pv = tampered_doc["proof"]["proofValue"]
        tampered_doc["proof"]["proofValue"] = original_pv[:-5] + "XXXXX"

        content_hash = hashlib.sha256(b"tampered-pv").hexdigest()
        tampered_pub = StatusListPublication(
            id=pub.id,
            status_list_id=pub.status_list_id,
            issuer_did=pub.issuer_did,
            status_purpose=pub.status_purpose,
            encoded_list=pub.encoded_list,
            content_hash=content_hash,
            document=tampered_doc,
            list_length=pub.list_length,
            capacity=pub.capacity,
            assigned_entries=pub.assigned_entries,
            revoked_entries=pub.revoked_entries,
            ttl_seconds=pub.ttl_seconds,
            etag=f'"{content_hash}-v1"',
            published_at=pub.published_at,
            created_at=pub.created_at,
            updated_at=pub.updated_at,
        )
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = tampered_pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "Status list proof validation failed" in result["details"]["evaluations"]["revocation"]

    def test_wrong_issuer_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )

        pub = _generate_status_list_publication(active_indices=[])
        wrong_issuer_doc = copy.deepcopy(dict(pub.document))
        wrong_issuer_doc["issuer"] = "did:web:attacker.example"

        content_hash = hashlib.sha256(b"wrong-issuer").hexdigest()
        wrong_pub = StatusListPublication(
            id=pub.id,
            status_list_id=pub.status_list_id,
            issuer_did=pub.issuer_did,
            status_purpose=pub.status_purpose,
            encoded_list=pub.encoded_list,
            content_hash=content_hash,
            document=wrong_issuer_doc,
            list_length=pub.list_length,
            capacity=pub.capacity,
            assigned_entries=pub.assigned_entries,
            revoked_entries=pub.revoked_entries,
            ttl_seconds=pub.ttl_seconds,
            etag=f'"{content_hash}-v1"',
            published_at=pub.published_at,
            created_at=pub.created_at,
            updated_at=pub.updated_at,
        )
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = wrong_pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_ISSUER_MISMATCH" in result["details"]["evaluations"]["revocation"]

    def test_missing_proof_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )

        pub = _generate_status_list_publication(active_indices=[])
        doc_no_proof = copy.deepcopy(dict(pub.document))
        doc_no_proof.pop("proof", None)

        content_hash = hashlib.sha256(b"no-proof").hexdigest()
        unproven_pub = StatusListPublication(
            id=pub.id,
            status_list_id=pub.status_list_id,
            issuer_did=pub.issuer_did,
            status_purpose=pub.status_purpose,
            encoded_list=pub.encoded_list,
            content_hash=content_hash,
            document=doc_no_proof,
            list_length=pub.list_length,
            capacity=pub.capacity,
            assigned_entries=pub.assigned_entries,
            revoked_entries=pub.revoked_entries,
            ttl_seconds=pub.ttl_seconds,
            etag=f'"{content_hash}-v1"',
            published_at=pub.published_at,
            created_at=pub.created_at,
            updated_at=pub.updated_at,
        )
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = unproven_pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_PROOF_MISSING" in result["details"]["evaluations"]["revocation"]

    def test_unsupported_proof_type_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )

        pub = _generate_status_list_publication(active_indices=[])
        bad_proof_doc = copy.deepcopy(dict(pub.document))
        bad_proof_doc["proof"]["type"] = "RsaSignature2018"

        content_hash = hashlib.sha256(b"bad-proof").hexdigest()
        unsupported_pub = StatusListPublication(
            id=pub.id,
            status_list_id=pub.status_list_id,
            issuer_did=pub.issuer_did,
            status_purpose=pub.status_purpose,
            encoded_list=pub.encoded_list,
            content_hash=content_hash,
            document=bad_proof_doc,
            list_length=pub.list_length,
            capacity=pub.capacity,
            assigned_entries=pub.assigned_entries,
            revoked_entries=pub.revoked_entries,
            ttl_seconds=pub.ttl_seconds,
            etag=f'"{content_hash}-v1"',
            published_at=pub.published_at,
            created_at=pub.created_at,
            updated_at=pub.updated_at,
        )
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = unsupported_pub
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_PROOF_UNSUPPORTED_TYPE" in result["details"]["evaluations"]["revocation"]

    def test_malformed_status_list_credential_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )
        publication = _generate_status_list_publication(active_indices=[])
        malformed_document = copy.deepcopy(dict(publication.document))
        malformed_document.pop("credentialSubject")
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = _publication_with_document(
            publication,
            malformed_document,
        )
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_CREDENTIAL_MALFORMED" in result["details"]["evaluations"]["revocation"]

    def test_invalid_status_list_proof_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )
        publication = _generate_status_list_publication(active_indices=[])
        invalid_document = copy.deepcopy(dict(publication.document))
        invalid_document["proof"]["proofValue"] = "z1234"
        mock_sl = MagicMock()
        mock_sl.get_publication.return_value = _publication_with_document(
            publication,
            invalid_document,
        )
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_PROOF_INVALID" in result["details"]["evaluations"]["revocation"]

    def test_untrusted_status_list_issuer_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )
        publication = _generate_status_list_publication(active_indices=[])
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )

        trusted_credential_issuer = SimpleNamespace(
            is_trusted=True,
            status=SimpleNamespace(value="ACTIVE"),
            reason="ISSUER_TRUST_VALID",
            trust_source="TEST",
            trust_record_id="credential-issuer-record",
        )
        untrusted_status_issuer = SimpleNamespace(
            is_trusted=False,
            status=None,
            reason="ISSUER_NOT_IN_TRUST_REGISTRY",
            trust_source=None,
            trust_record_id=None,
        )
        mock_trust_registry = MagicMock()
        mock_trust_registry.evaluate_issuer_trust.side_effect = [
            trusted_credential_issuer,
            untrusted_status_issuer,
        ]
        app.dependency_overrides[get_trust_registry_service] = (
            lambda: mock_trust_registry
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_ISSUER_NOT_TRUSTED" in result["details"]["evaluations"]["revocation"]

    def test_status_list_trust_registry_error_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=10,
        )
        publication = _generate_status_list_publication(active_indices=[])
        mock_sl_service = MagicMock()
        mock_sl_service.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = lambda: mock_sl_service

        trusted_credential_issuer = SimpleNamespace(
            is_trusted=True,
            status=SimpleNamespace(value="ACTIVE"),
            reason="ISSUER_TRUST_VALID",
            trust_source="TEST",
            trust_record_id="credential-issuer-record",
        )
        mock_trust_registry = MagicMock()
        mock_trust_registry.evaluate_issuer_trust.side_effect = [
            trusted_credential_issuer,
            TimeoutError("status-list trust registry timed out"),
        ]
        app.dependency_overrides[get_trust_registry_service] = (
            lambda: mock_trust_registry
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )

        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "STATUS_LIST_TRUST_REGISTRY_ERROR:TimeoutError" in result["details"]["evaluations"]["revocation"]

    def test_status_index_outside_published_list_fails_closed(self):
        headers = _verifier_headers()
        session = _create_session(headers)
        vp_token = _make_vc_with_status(
            nonce=session["nonce"],
            status_list_index=131072,
        )
        publication = _generate_status_list_publication(active_indices=[])
        mock_status_lists = MagicMock()
        mock_status_lists.get_publication.return_value = publication
        app.dependency_overrides[get_status_list_service] = (
            lambda: mock_status_lists
        )

        res = client.post(
            "/api/v1/oid4vp/response",
            json={"sessionId": session["sessionId"], "vpToken": vp_token},
            headers=headers,
        )
        assert res.status_code == 200
        result = res.json()["result"]
        assert result["finalPolicyResult"] == "REJECTED"
        assert result["revocationStatusClear"] is False
        assert "statusListIndex is outside the published list" in result["details"]["evaluations"]["revocation"]
