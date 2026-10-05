from __future__ import annotations

import copy
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.domain.dcql import (
    DcqlQuery,
    DcqlCredentialQuery,
    DcqlClaimQuery,
    DcqlCredentialSet,
    MalformedDcqlQueryError,
)
from app.application.services.dcql_engine import (
    DcqlEngine,
    build_dcql_query_from_types_and_fields,
    convert_legacy_presentation_definition_to_dcql,
)
from app.infrastructure.crypto.local_holder_key_provider import SYNTHETIC_HOLDER_DID
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
    build_signed_presentation,
)

client = TestClient(app)

PASSWORDS = {
    "holder": "Holder-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
}


def _get_verifier_token() -> str:
    res = client.post(
        "/api/v1/auth/token",
        json={"username": "verifier@example.test", "password": PASSWORDS["verifier"]},
    )
    assert res.status_code == 200, f"Verifier auth failed: {res.text}"
    return res.json()["accessToken"]


def _build_signed_vc(
    *,
    credential_type: str = "UniversityAffiliationCredential",
    claims: dict[str, Any] | None = None,
    holder_did: str = SYNTHETIC_HOLDER_DID,
    issuer_did: str = "did:web:issuer.example",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    raw_vc = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", credential_type],
        "issuer": issuer_did,
        "validFrom": (now - timedelta(days=10)).isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": holder_did,
            "affiliation": "student",
            "programCode": "SYN-CS-2026",
            "degree": "Master of Science",
            "graduationYear": 2026,
            **(claims or {}),
        },
    }
    proof_service = build_local_proof_service(clock=lambda: now)
    return proof_service.sign_credential(raw_vc)


def _build_raw_vc(
    *,
    credential_type: str = "UniversityAffiliationCredential",
    claims: dict[str, Any] | None = None,
    holder_did: str = SYNTHETIC_HOLDER_DID,
) -> dict[str, Any]:
    return {
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", credential_type],
        "credentialSubject": {
            "id": holder_did,
            **(claims or {}),
        },
    }


# ==============================================================================
# SECTION A: PROTOCOL & AUTHORIZATION REQUEST TESTS (OID4VP 1.0)
# ==============================================================================


def test_wp04_verifier_request_generates_canonical_dcql_query():
    """Canonical verifier request must produce OID4VP 1.0 request with dcql_query."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "purpose": "Academic and degree verification",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree", "graduationYear"],
        "ttlSeconds": 600,
    }
    res = client.post("/api/v1/oid4vp/requests", json=payload, headers=headers)
    assert res.status_code == 201, f"Request failed: {res.text}"
    data = res.json()

    # Verify canonical OID4VP 1.0 fields
    assert "dcqlQuery" in data or "dcql_query" in data
    dcql = data.get("dcqlQuery") or data.get("dcql_query")
    assert isinstance(dcql, dict)
    assert "credentials" in dcql
    assert len(dcql["credentials"]) == 1
    assert dcql["credentials"][0]["meta"]["type_values"] == ["UniversityAffiliationCredential"]

    # Verify deep link URI structure conforms to OID4VP 1.0
    deep_link = data["deepLinkUri"]
    assert deep_link.startswith("openid4vp://")
    parsed = urllib.parse.urlparse(deep_link)
    params = urllib.parse.parse_qs(parsed.query)

    assert params.get("response_type") == ["vp_token"]
    assert params.get("response_mode") == ["direct_post"]
    assert "client_id" in params
    assert "nonce" in params
    assert params.get("state") == [data["sessionId"]]
    assert "dcql_query" in params

    # Legacy presentation_definition is retained as a compatibility artifact
    assert "presentationDefinition" in data or "presentation_definition" in data


def test_wp04_verifier_request_with_explicit_dcql_query():
    """Verifier can provide explicit DCQL query which is validated and persisted."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    explicit_dcql = {
        "credentials": [
            {
                "id": "degree_query",
                "format": "w3c_vc",
                "meta": {
                    "type_values": ["UniversityAffiliationCredential"]
                },
                "claims": [
                    {"id": "c_degree", "path": ["credentialSubject", "degree"]},
                    {"id": "c_grad", "path": ["credentialSubject", "graduationYear"]},
                ],
            }
        ],
        "credential_sets": [
            {
                "options": [["degree_query"]],
                "purpose": "Need university degree",
                "required": True,
            }
        ],
    }

    payload = {
        "purpose": "Explicit DCQL verification",
        "requestedCredentialTypes": ["UniversityAffiliationCredential"],
        "requestedFields": ["degree", "graduationYear"],
        "dcqlQuery": explicit_dcql,
    }
    res = client.post("/api/v1/oid4vp/requests", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    returned_dcql = data.get("dcqlQuery") or data.get("dcql_query")
    assert returned_dcql["credentials"][0]["id"] == "degree_query"


def test_wp04_verifier_request_with_malformed_dcql_query_fails_closed():
    """Malformed DCQL query in session creation must fail closed with 400 Bad Request."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    malformed_dcql = {
        "credentials": [
            {
                # Missing 'id'
                "format": "w3c_vc",
                "claims": [],
            }
        ]
    }
    payload = {
        "purpose": "Malformed DCQL test",
        "dcqlQuery": malformed_dcql,
    }
    res = client.post("/api/v1/oid4vp/requests", json=payload, headers=headers)
    assert res.status_code == 400 or res.status_code == 422


# ==============================================================================
# SECTION B: REQUIRED DCQL SCENARIOS (A - G)
# ==============================================================================


def test_wp04_scenario_a_single_credential_specific_claims():
    """Scenario A: Single credential with requested claims satisfied."""
    query = build_dcql_query_from_types_and_fields(
        requested_types=["UniversityAffiliationCredential"],
        requested_fields=["degree", "graduationYear"],
    )
    vc = _build_raw_vc(
        credential_type="UniversityAffiliationCredential",
        claims={"degree": "Master of Science", "graduationYear": 2026},
    )
    result = DcqlEngine.evaluate(query, [vc])

    assert result.is_satisfied is True
    assert len(result.matched_credentials) == 1
    match = result.matched_credentials[0]
    assert match.query_id == "query_1"
    assert "claim_degree" in match.matched_claims
    assert match.matched_claims["claim_degree"] == "Master of Science"
    assert "claim_graduationyear" in match.matched_claims
    assert match.matched_claims["claim_graduationyear"] == 2026


def test_wp04_scenario_b_unsatisfied_query_no_accidental_presentation():
    """Scenario B: Query requires ResidenceCredential, wallet only has University credential -> fails closed."""
    query = build_dcql_query_from_types_and_fields(
        requested_types=["ResidenceCredential"],
        requested_fields=["address", "city"],
    )
    vc = _build_raw_vc(
        credential_type="UniversityAffiliationCredential",
        claims={"degree": "Master of Science", "graduationYear": 2026},
    )
    result = DcqlEngine.evaluate(query, [vc])

    assert result.is_satisfied is False
    assert result.unsatisfied_reason is not None
    assert "UNSATISFIED" in result.unsatisfied_reason
    assert len(result.matched_credentials) == 0


def test_wp04_scenario_c_credential_set_alternatives():
    """Scenario C: Credential set with alternative options (Passport OR ID Card)."""
    query = DcqlQuery(
        credentials=(
            DcqlCredentialQuery(
                id="passport_query",
                format="w3c_vc",
                type_values=("PassportCredential",),
                claims=(DcqlClaimQuery(id="c_doc", path=("credentialSubject", "doc_number")),),
            ),
            DcqlCredentialQuery(
                id="idcard_query",
                format="w3c_vc",
                type_values=("NationalIdentityCredential",),
                claims=(DcqlClaimQuery(id="c_id", path=("credentialSubject", "id_number")),),
            ),
        ),
        credential_sets=(
            DcqlCredentialSet(
                options=(("passport_query",), ("idcard_query",)),
                purpose="Identity document (passport or ID card)",
                required=True,
            ),
        ),
    )

    # Wallet holds ONLY NationalIdentityCredential
    idcard_vc = _build_raw_vc(
        credential_type="NationalIdentityCredential",
        claims={"id_number": "12345678901"},
    )
    result = DcqlEngine.evaluate(query, [idcard_vc])

    assert result.is_satisfied is True
    assert len(result.matched_credentials) == 1
    assert result.matched_credentials[0].query_id == "idcard_query"


def test_wp04_scenario_d_claim_value_matching():
    """Scenario D: Value matching - exact match succeeds, mismatch fails closed."""
    query = DcqlQuery(
        credentials=(
            DcqlCredentialQuery(
                id="citizenship_query",
                format="w3c_vc",
                type_values=("NationalIdentityCredential",),
                claims=(
                    DcqlClaimQuery(
                        id="c_country",
                        path=("credentialSubject", "country"),
                        values=("TR", "DE"),
                    ),
                ),
            ),
        )
    )

    # 1. Matching value ("TR")
    vc_match = _build_raw_vc(
        credential_type="NationalIdentityCredential",
        claims={"country": "TR"},
    )
    res_match = DcqlEngine.evaluate(query, [vc_match])
    assert res_match.is_satisfied is True

    # 2. Mismatched value ("FR")
    vc_mismatch = _build_raw_vc(
        credential_type="NationalIdentityCredential",
        claims={"country": "FR"},
    )
    matched, _, reason = DcqlEngine.evaluate_credential_query(query.credentials[0], vc_mismatch)
    assert not matched
    assert "does not match allowed values" in (reason or "")

    res_mismatch = DcqlEngine.evaluate(query, [vc_mismatch])
    assert res_mismatch.is_satisfied is False
    assert "UNSATISFIED" in (res_mismatch.unsatisfied_reason or "")


def test_wp04_scenario_e_unknown_credential_format_rejected():
    """Scenario E: Query specifying unsupported format fails closed."""
    query = DcqlQuery(
        credentials=(
            DcqlCredentialQuery(
                id="unsupported_format_query",
                format="unknown_custom_crypto_format_v99",
                type_values=("AnyCredential",),
            ),
        )
    )
    vc = _build_raw_vc()
    matched, _, reason = DcqlEngine.evaluate_credential_query(query.credentials[0], vc)
    assert not matched
    assert "Unsupported credential format" in (reason or "")

    res = DcqlEngine.evaluate(query, [vc])
    assert res.is_satisfied is False
    assert "UNSATISFIED" in (res.unsatisfied_reason or "")


def test_wp04_scenario_f_malformed_dcql_rejected_safely():
    """Scenario F: Malformed DCQL structures raise MalformedDcqlQueryError or return unsatisfied result."""
    with pytest.raises(MalformedDcqlQueryError):
        # Empty query id
        DcqlCredentialQuery(id="", format="w3c_vc")

    with pytest.raises(MalformedDcqlQueryError):
        # Duplicate claim query IDs
        DcqlCredentialQuery(
            id="q1",
            format="w3c_vc",
            claims=(
                DcqlClaimQuery(id="dup", path=("credentialSubject", "a")),
                DcqlClaimQuery(id="dup", path=("credentialSubject", "b")),
            ),
        )

    # Engine evaluate with raw malformed mapping fails closed
    malformed_dict = {"credentials": [{"invalid": True}]}
    eval_res = DcqlEngine.evaluate(malformed_dict, [_build_raw_vc()])
    assert eval_res.is_satisfied is False
    assert "MALFORMED_DCQL_QUERY" in (eval_res.unsatisfied_reason or "")


def test_wp04_scenario_g_pe_legacy_migration_and_conversion():
    """Scenario G: Legacy PE presentation definitions can be safely converted to DCQL."""
    legacy_pe = {
        "id": "legacy_pe_req",
        "input_descriptors": [
            {
                "id": "descriptor_univ",
                "schema": [{"uri": "https://schema.org/UniversityAffiliationCredential"}],
                "constraints": {
                    "fields": [
                        {"path": ["$.credentialSubject.degree"]},
                        {"path": ["$.credentialSubject.graduationYear"]},
                    ]
                },
            }
        ],
    }

    converted = convert_legacy_presentation_definition_to_dcql(legacy_pe)
    assert len(converted.credentials) == 1
    assert converted.credentials[0].id == "descriptor_univ"
    assert "UniversityAffiliationCredential" in converted.credentials[0].type_values

    # Test evaluation with converted DCQL
    vc = _build_raw_vc(
        credential_type="UniversityAffiliationCredential",
        claims={"degree": "Master of Science", "graduationYear": 2026},
    )
    result = DcqlEngine.evaluate(converted, [vc])
    assert result.is_satisfied is True


# ==============================================================================
# SECTION C: WALLET EVALUATION ENDPOINT INTEGRATION
# ==============================================================================


def test_wp04_wallet_evaluation_api_satisfied():
    """Holder wallet evaluates candidate credentials against session DCQL query (match found)."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Holder wallet pre-consent check",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree", "graduationYear"],
        },
        headers=headers,
    )
    session_id = session_res.json()["sessionId"]

    candidate_vc = _build_raw_vc(
        credential_type="UniversityAffiliationCredential",
        claims={"degree": "Master of Science", "graduationYear": 2026},
    )

    eval_res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/evaluate-dcql",
        json={"candidateCredentials": [candidate_vc]},
    )
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert data["isSatisfied"] is True
    assert len(data["matchedCredentials"]) == 1
    matched = data["matchedCredentials"][0]
    matched_claims = matched.get("matchedClaims") or matched.get("matched_claims") or {}
    assert "claim_degree" in matched_claims


def test_wp04_wallet_evaluation_api_unsatisfied():
    """Holder wallet evaluates candidate credentials against session DCQL query (no match found)."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Holder wallet pre-consent check",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree", "graduationYear"],
        },
        headers=headers,
    )
    session_id = session_res.json()["sessionId"]

    # Candidate has different type
    candidate_vc = _build_raw_vc(
        credential_type="DrivingLicenseCredential",
        claims={"license_class": "B"},
    )

    eval_res = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/evaluate-dcql",
        json={"candidateCredentials": [candidate_vc]},
    )
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert data["isSatisfied"] is False
    assert data["unsatisfiedReason"] is not None
    assert len(data["matchedCredentials"]) == 0


# ==============================================================================
# SECTION D: VERIFIER DIRECT POST INTEGRATION & FAIL-CLOSED ENFORCEMENT
# ==============================================================================


def test_wp04_direct_post_satisfying_dcql_accepted():
    """Valid presentation satisfying session DCQL query results in ACCEPTED."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Direct Post DCQL Test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree", "graduationYear"],
        },
        headers=headers,
    )
    session_data = session_res.json()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    vc = _build_signed_vc()

    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp,
            "disclosedClaims": {"degree": "Master of Science", "graduationYear": 2026},
            "aiRiskScore": 10,
        },
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["finalPolicyResult"] == "ACCEPTED"
    assert res_data["signatureValid"] is True
    assert res_data["holderBindingValid"] is True
    assert res_data["issuerTrusted"] is True
    assert res_data["details"]["evaluations"]["dcql"] == "DCQL query criteria fully satisfied"
    assert res_data["details"]["dcql"]["satisfied"] is True


def test_wp04_direct_post_mismatched_credential_type_fails_closed():
    """Validly signed credential of wrong type fails DCQL evaluation -> REJECTED."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    # Verifier specifically requests a StrictGovernmentIdCredential
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Direct Post DCQL Mismatch Test",
            "requestedCredentialTypes": ["StrictGovernmentIdCredential"],
            "requestedFields": ["national_identifier"],
        },
        headers=headers,
    )
    session_data = session_res.json()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    # Present UniversityAffiliationCredential instead
    vc_different_type = _build_signed_vc()

    vp = build_signed_presentation(
        vc_different_type,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp,
            "disclosedClaims": {"degree": "Master of Science"},
            "aiRiskScore": 10,
        },
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["finalPolicyResult"] == "REJECTED"
    assert res_data["details"]["dcql"]["satisfied"] is False
    assert "UNSATISFIED" in res_data["details"]["dcql"]["reason"]


def test_wp04_direct_post_missing_required_claim_fails_closed():
    """Credential with missing requested claim fails DCQL evaluation -> REJECTED."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Direct Post Missing Claim Test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree", "special_honors_award"],  # special_honors_award is not present
        },
        headers=headers,
    )
    session_data = session_res.json()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    vc = _build_signed_vc()  # special_honors_award absent

    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": session_id,
            "vpToken": vp,
            "disclosedClaims": {"degree": "Master of Science"},
            "aiRiskScore": 10,
        },
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["finalPolicyResult"] == "REJECTED"
    assert res_data["details"]["dcql"]["satisfied"] is False


# ==============================================================================
# SECTION E: SECURITY REGRESSION TESTS (WP-01, WP-02, WP-03 GUARANTEES)
# ==============================================================================


def test_wp04_security_regression_invalid_signature_fails_closed():
    """Tampered VC signature must still fail closed (WP-01 invariant)."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Sig tamper test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree"],
        },
        headers=headers,
    )
    session_data = session_res.json()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    vc = _build_signed_vc()
    # Tamper claim after signing
    vc["credentialSubject"]["degree"] = "TAMPERED_DEGREE"

    vp = build_signed_presentation(
        vc,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp, "aiRiskScore": 10},
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["signatureValid"] is False
    assert res_data["finalPolicyResult"] == "REJECTED"


def test_wp04_security_regression_wrong_nonce_fails_closed():
    """VP challenge nonce mismatch must fail closed (WP-01/WP-02 invariant)."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Wrong nonce test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree"],
        },
        headers=headers,
    )
    session_data = session_res.json()
    session_id = session_data["sessionId"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    vc = _build_signed_vc()
    vp = build_signed_presentation(
        vc,
        nonce="wrong-nonce-1234567890",
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp, "aiRiskScore": 10},
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["challengeValid"] is False
    assert res_data["finalPolicyResult"] == "REJECTED"


def test_wp04_security_regression_wrong_holder_key_fails_closed():
    """VP signed with an unauthorized key must fail closed (WP-02 invariant)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from app.infrastructure.crypto.multibase import encode_base58_btc
    from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer

    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Wrong holder key test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree"],
        },
        headers=headers,
    )
    session_data = session_res.json()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    vc = _build_signed_vc()
    # Sign VP using an ephemeral, unassociated key
    attacker_key = Ed25519PrivateKey.generate()

    unsecured_vp = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": ["VerifiablePresentation"],
        "verifiableCredential": [vc],
        "holder": SYNTHETIC_HOLDER_DID,
    }
    proof_config = {
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "proofPurpose": "authentication",
        "verificationMethod": f"{SYNTHETIC_HOLDER_DID}#key-1",
        "challenge": nonce,
        "domain": client_id,
    }
    canonicalizer = JcsCanonicalizer()
    signing_input = canonicalizer.create_signing_input(unsecured_vp, proof_config)
    sig_bytes = attacker_key.sign(signing_input)
    proof_config["proofValue"] = encode_base58_btc(sig_bytes)
    vp = {**unsecured_vp, "proof": proof_config}

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp, "aiRiskScore": 10},
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["holderBindingValid"] is False
    assert res_data["finalPolicyResult"] == "REJECTED"


def test_wp04_security_regression_untrusted_issuer_fails_closed():
    """Credential issued by an untrusted DID must fail closed (WP-03 invariant)."""
    token = _get_verifier_token()
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Untrusted issuer test",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree"],
        },
        headers=headers,
    )
    session_data = session_res.json()
    session_id = session_data["sessionId"]
    nonce = session_data["nonce"]
    client_id = session_data.get("clientId", "http://testserver/verifier")

    now = datetime.now(UTC)
    untrusted_did = "did:web:rogue-untrusted-issuer.org"
    vc_untrusted = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "UniversityAffiliationCredential"],
        "issuer": untrusted_did,
        "validFrom": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "validUntil": (now + timedelta(days=365)).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": SYNTHETIC_HOLDER_DID,
            "degree": "Master of Science",
            "graduationYear": 2026,
        },
        "proof": {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "created": now.isoformat().replace("+00:00", "Z"),
            "verificationMethod": f"{untrusted_did}#key-1",
            "proofPurpose": "assertionMethod",
            "proofValue": "zMockProofValueForUntrustedIssuer",
        },
    }

    vp = build_signed_presentation(
        vc_untrusted,
        nonce=nonce,
        domain=client_id,
        holder_did=SYNTHETIC_HOLDER_DID,
    )

    post_res = client.post(
        "/api/v1/oid4vp/response",
        json={"sessionId": session_id, "vpToken": vp, "aiRiskScore": 10},
    )
    assert post_res.status_code == 200
    res_data = post_res.json()["result"]
    assert res_data["issuerTrusted"] is False
    assert res_data["finalPolicyResult"] == "REJECTED"
