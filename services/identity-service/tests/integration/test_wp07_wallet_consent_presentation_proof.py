from __future__ import annotations

from collections.abc import Iterator
import time
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_audit_event_repository,
    get_mongo_connection_manager,
)
from app.application.services.credential_proof_service import CredentialProofService
from app.main import app
from app.infrastructure.fixtures.signed_credentials import build_signed_presentation


PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient, role: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": f"{role}@example.test",
            "password": PASSWORDS[role],
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _create_wallet(
    client: TestClient,
    holder_headers: dict[str, str],
) -> dict[str, str]:
    response = client.post(
        "/api/v1/wallets",
        json={},
        headers=holder_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _issue_credential(
    client: TestClient,
    *,
    wallet: dict[str, str],
    issuer_headers: dict[str, str],
    holder_headers: dict[str, str],
) -> dict[str, Any]:
    offer_response = client.post(
        "/api/v1/oid4vci/offers",
        json={
            "credentialConfigurationIds": ["UniversityAffiliationCredential"],
            "subjectData": {
                "affiliation": "student",
                "programCode": "SYN-CS-2026",
                "degree": "Master of Science",
                "graduationYear": 2026,
                "holder_did": wallet["holderDid"],
            },
            "ttlSeconds": 1800,
        },
        headers=issuer_headers,
    )
    assert offer_response.status_code == 201, offer_response.text
    code = offer_response.json()["preAuthorizedCode"]

    token_response = client.post(
        "/api/v1/oid4vci/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
            "pre-authorized_code": code,
        },
    )
    assert token_response.status_code == 200, token_response.text
    token = token_response.json()

    metadata_response = client.get(
        "/api/v1/oid4vci/.well-known/openid-credential-issuer"
    )
    assert metadata_response.status_code == 200, metadata_response.text
    proof_response = client.post(
        "/api/v1/oid4vci/holder-proof",
        json={
            "walletId": wallet["walletId"],
            "audience": metadata_response.json()["credential_issuer"],
            "nonce": token["c_nonce"],
        },
        headers=holder_headers,
    )
    assert proof_response.status_code == 200, proof_response.text
    assert proof_response.json()["holderDid"] == wallet["holderDid"]

    credential_response = client.post(
        "/api/v1/oid4vci/credential",
        json={
            "credentialConfigurationId": "UniversityAffiliationCredential",
            "walletId": wallet["walletId"],
            "proof": {
                "proofType": "jwt",
                "jwt": proof_response.json()["jwt"],
            },
        },
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    assert credential_response.status_code == 200, credential_response.text
    credential = credential_response.json()["credential"]
    assert credential["credentialSubject"]["id"] == wallet["holderDid"]
    return credential


def _create_session(
    client: TestClient,
    verifier_headers: dict[str, str],
    *,
    requested_types: list[str] | None = None,
    requested_fields: list[str] | None = None,
    ttl_seconds: int = 600,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Verify academic affiliation for a security review",
            "requestedCredentialTypes": (
                requested_types or ["UniversityAffiliationCredential"]
            ),
            "requestedFields": requested_fields
            or ["affiliation", "programCode", "degree", "graduationYear"],
            "ttlSeconds": ttl_seconds,
        },
        headers=verifier_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _flow(
    client: TestClient,
    *,
    requested_types: list[str] | None = None,
) -> dict[str, Any]:
    holder_headers = _headers(client, "holder")
    issuer_headers = _headers(client, "issuer")
    verifier_headers = _headers(client, "verifier")
    wallet = _create_wallet(client, holder_headers)
    credential = _issue_credential(
        client,
        wallet=wallet,
        issuer_headers=issuer_headers,
        holder_headers=holder_headers,
    )
    session = _create_session(
        client,
        verifier_headers,
        requested_types=requested_types,
    )
    claims = {
        key: value
        for key, value in credential["credentialSubject"].items()
        if key != "id"
    }
    return {
        "holder_headers": holder_headers,
        "issuer_headers": issuer_headers,
        "verifier_headers": verifier_headers,
        "wallet": wallet,
        "credential": credential,
        "session": session,
        "claims": claims,
    }


def _consent(
    client: TestClient,
    flow: dict[str, Any],
    *,
    action: str = "APPROVE",
    claims: dict[str, Any] | None = None,
    credential_ids: list[str] | None = None,
    wallet: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    selected_wallet = wallet or flow["wallet"]
    selected_credentials = credential_ids
    if selected_credentials is None:
        selected_credentials = (
            [flow["credential"]["id"]] if action == "APPROVE" else []
        )
    approved_claims = claims
    if approved_claims is None:
        approved_claims = flow["claims"] if action == "APPROVE" else {}
    return client.post(
        f"/api/v1/oid4vp/requests/{flow['session']['sessionId']}/wallet-consent",
        json={
            "walletId": selected_wallet["walletId"],
            "holderDid": selected_wallet["holderDid"],
            "action": action,
            "approvedCredentials": selected_credentials,
            "approvedClaims": approved_claims,
            "rejectionReason": (
                "Holder declined this presentation"
                if action == "REJECT"
                else None
            ),
        },
        headers=headers or flow["holder_headers"],
    )


def _create_wallet_presentation(
    client: TestClient,
    flow: dict[str, Any],
    *,
    session_id: str | None = None,
    credential_ids: list[str] | None = None,
    claims: dict[str, Any] | None = None,
) -> Any:
    return client.post(
        "/api/v1/oid4vp/wallet-presentation",
        json={
            "sessionId": session_id or flow["session"]["sessionId"],
            "walletId": flow["wallet"]["walletId"],
            "credentialIds": credential_ids
            if credential_ids is not None
            else [flow["credential"]["id"]],
            "disclosedClaims": flow["claims"] if claims is None else claims,
        },
        headers=flow["holder_headers"],
    )


def test_wallet_bound_golden_path_uses_complete_signed_credential(
    client: TestClient,
) -> None:
    flow = _flow(client)
    credential = flow["credential"]

    inventory = client.get(
        f"/api/v1/wallets/{flow['wallet']['walletId']}/credentials",
        headers=flow["holder_headers"],
    )
    assert inventory.status_code == 200, inventory.text
    assert any(
        item["credentialId"] == credential["id"]
        for item in inventory.json()["credentials"]
    )

    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text
    assert consent.json()["status"] == "PENDING"
    assert consent.json()["action"] == "APPROVE"
    assert set(consent.json()["approvedClaims"]) == set(flow["claims"])

    presentation = _create_wallet_presentation(client, flow)
    assert presentation.status_code == 200, presentation.text
    vp_token = presentation.json()["vpToken"]
    embedded_vc = vp_token["verifiableCredential"][0]
    assert embedded_vc == credential
    assert embedded_vc["proof"] == credential["proof"]
    assert vp_token["proof"]["type"] == "DataIntegrityProof"
    assert vp_token["proof"]["cryptosuite"] == "eddsa-jcs-2022"
    assert vp_token["proof"]["proofPurpose"] == "authentication"
    assert vp_token["proof"]["challenge"] == flow["session"]["nonce"]
    assert vp_token["proof"]["proofValue"] != "zMockHolderPresentationProofValue2026"

    direct_post = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": flow["session"]["sessionId"],
            "vpToken": vp_token,
            "disclosedClaims": flow["claims"],
        },
    )
    assert direct_post.status_code == 200, direct_post.text
    result = direct_post.json()["result"]
    assert result["finalPolicyResult"] == "ACCEPTED"
    assert result["signatureValid"] is True
    assert result["holderBindingValid"] is True
    assert result["challengeValid"] is True
    assert result["details"]["evaluations"]["consent"] == "Authorized by holder consent"
    minimization = result["details"]["dataMinimization"]
    assert minimization["status"] == "FULL_CREDENTIAL_DISCLOSED"
    assert minimization["hiddenFields"] == []
    assert minimization["selectiveDisclosureActive"] is False
    assert minimization["cryptographicSelectiveDisclosure"] is False


def test_holder_rejection_blocks_presentation_and_direct_post(
    client: TestClient,
) -> None:
    flow = _flow(client)
    rejection = _consent(client, flow, action="REJECT")
    assert rejection.status_code == 200, rejection.text
    assert rejection.json()["status"] == "REJECTED"
    assert rejection.json()["consentStatus"] == "REJECTED"

    presentation = _create_wallet_presentation(client, flow)
    assert presentation.status_code == 409

    direct_post = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": flow["session"]["sessionId"],
            "vpToken": {},
        },
    )
    assert direct_post.status_code == 409
    status_response = client.get(
        f"/api/v1/oid4vp/requests/{flow['session']['sessionId']}",
        headers=flow["verifier_headers"],
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "REJECTED"


def test_wallet_consent_and_presentation_require_holder_authentication(
    client: TestClient,
) -> None:
    flow = _flow(client)
    session_id = flow["session"]["sessionId"]

    consent = client.post(
        f"/api/v1/oid4vp/requests/{session_id}/wallet-consent",
        json={
            "walletId": flow["wallet"]["walletId"],
            "holderDid": flow["wallet"]["holderDid"],
            "action": "REJECT",
        },
    )
    presentation = client.post(
        "/api/v1/oid4vp/wallet-presentation",
        json={
            "sessionId": session_id,
            "walletId": flow["wallet"]["walletId"],
            "credentialIds": [flow["credential"]["id"]],
            "disclosedClaims": flow["claims"],
        },
    )
    assert consent.status_code == 401
    assert presentation.status_code == 401


def test_verifier_cannot_submit_holder_consent(
    client: TestClient,
) -> None:
    flow = _flow(client)
    response = _consent(
        client,
        flow,
        action="REJECT",
        headers=flow["verifier_headers"],
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"]


def test_wallet_did_is_derived_from_authenticated_wallet(
    client: TestClient,
) -> None:
    flow = _flow(client)
    response = _consent(client, flow, action="REJECT")
    assert response.status_code == 200, response.text

    forged = client.post(
        f"/api/v1/oid4vp/requests/{flow['session']['sessionId']}/wallet-consent",
        json={
            "walletId": flow["wallet"]["walletId"],
            "holderDid": "did:key:attacker",
            "action": "REJECT",
        },
        headers=flow["holder_headers"],
    )
    assert forged.status_code == 400


def test_partial_claim_consent_is_rejected_without_changing_session(
    client: TestClient,
) -> None:
    flow = _flow(client)
    partial = {"degree": flow["claims"]["degree"]}
    response = _consent(client, flow, claims=partial)
    assert response.status_code == 400
    assert "complete signed credential" in response.json()["error"]["message"]

    status_response = client.get(
        f"/api/v1/oid4vp/requests/{flow['session']['sessionId']}",
        headers=flow["verifier_headers"],
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "PENDING"
    assert status_response.json()["consentStatus"] == "PENDING"


def test_rejected_claims_cannot_be_combined_with_full_credential_approval(
    client: TestClient,
) -> None:
    flow = _flow(client)
    response = client.post(
        f"/api/v1/oid4vp/requests/{flow['session']['sessionId']}/wallet-consent",
        json={
            "walletId": flow["wallet"]["walletId"],
            "holderDid": flow["wallet"]["holderDid"],
            "action": "APPROVE",
            "approvedCredentials": [flow["credential"]["id"]],
            "approvedClaims": flow["claims"],
            "rejectedClaims": ["degree"],
        },
        headers=flow["holder_headers"],
    )
    assert response.status_code == 400
    assert "complete signed credential" in response.json()["error"]["message"]


def test_wallet_consent_rejects_client_supplied_session_context(
    client: TestClient,
) -> None:
    flow = _flow(client)
    response = client.post(
        f"/api/v1/oid4vp/requests/{flow['session']['sessionId']}/wallet-consent",
        json={
            "walletId": flow["wallet"]["walletId"],
            "holderDid": flow["wallet"]["holderDid"],
            "action": "REJECT",
            "nonce": "attacker-selected-nonce",
            "clientId": "https://attacker.example",
            "verifierDid": "did:web:attacker.example",
            "purpose": "Attacker-selected purpose",
        },
        headers=flow["holder_headers"],
    )
    assert response.status_code == 422

    status_response = client.get(
        f"/api/v1/oid4vp/requests/{flow['session']['sessionId']}",
        headers=flow["verifier_headers"],
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "PENDING"


def test_empty_credential_selection_cannot_be_approved(
    client: TestClient,
) -> None:
    flow = _flow(client)
    response = _consent(client, flow, credential_ids=[])
    assert response.status_code == 400
    message = response.json()["error"]["message"]
    assert "does not satisfy" in message or "credential" in message.casefold()


def test_expired_session_cannot_record_consent(
    client: TestClient,
) -> None:
    flow = _flow(client)
    flow["session"] = _create_session(
        client,
        flow["verifier_headers"],
        ttl_seconds=1,
    )
    time.sleep(1.05)
    response = _consent(client, flow)
    assert response.status_code == 410


def test_presentation_without_consent_is_rejected(
    client: TestClient,
) -> None:
    flow = _flow(client)
    response = _create_wallet_presentation(client, flow)
    assert response.status_code == 409


def test_dcql_mismatch_cannot_be_approved(
    client: TestClient,
) -> None:
    flow = _flow(client, requested_types=["DegreeCredential"])
    response = _consent(client, flow)
    assert response.status_code == 400
    assert "DCQL query" in response.json()["error"]["message"]


def test_empty_requested_credential_types_are_rejected(
    client: TestClient,
) -> None:
    verifier_headers = _headers(client, "verifier")
    response = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Reject an empty verifier query",
            "requestedCredentialTypes": [],
            "requestedFields": ["degree"],
        },
        headers=verifier_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"]


def test_second_wallet_cannot_present_first_wallet_credential(
    client: TestClient,
) -> None:
    flow = _flow(client)
    second_wallet = _create_wallet(client, flow["holder_headers"])
    response = _consent(client, flow, wallet=second_wallet)
    assert response.status_code == 400
    assert "DCQL query" in response.json()["error"]["message"]


def test_consent_is_bound_to_its_session(
    client: TestClient,
) -> None:
    flow = _flow(client)
    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text
    other_session = _create_session(client, flow["verifier_headers"])

    response = _create_wallet_presentation(
        client,
        flow,
        session_id=other_session["sessionId"],
    )
    assert response.status_code == 409


def test_presentation_cannot_exceed_approved_credentials_or_claims(
    client: TestClient,
) -> None:
    flow = _flow(client)
    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text

    extra_credential = _create_wallet_presentation(
        client,
        flow,
        credential_ids=[flow["credential"]["id"], "urn:uuid:attacker-credential"],
    )
    assert extra_credential.status_code == 400

    changed_claims = dict(flow["claims"])
    changed_claims["degree"] = "Forged Degree"
    changed_presentation = _create_wallet_presentation(
        client,
        flow,
        claims=changed_claims,
    )
    assert changed_presentation.status_code == 400


def test_tampered_issuer_credential_fails_direct_post(
    client: TestClient,
) -> None:
    flow = _flow(client)
    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text
    presentation = _create_wallet_presentation(client, flow)
    assert presentation.status_code == 200, presentation.text
    vp_token = presentation.json()["vpToken"]
    vp_token["verifiableCredential"][0]["credentialSubject"]["degree"] = (
        "Forged Degree"
    )

    response = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": flow["session"]["sessionId"],
            "vpToken": vp_token,
            "disclosedClaims": flow["claims"],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["signatureValid"] is False
    assert result["finalPolicyResult"] == "REJECTED"


def test_valid_holder_proof_cannot_hide_tampered_issuer_credential(
    client: TestClient,
) -> None:
    flow = _flow(client)
    from app.api.v1 import dependencies

    manager = dependencies.get_mongo_connection_manager()
    wallet = dependencies.get_holder_wallet_repository(manager=manager).get(
        flow["wallet"]["walletId"]
    )
    assert wallet is not None
    development_provider = dependencies._KEY_PROVIDERS["development"]
    holder_private_key = development_provider._private_key(wallet.key_reference)
    tampered_credential = {
        **flow["credential"],
        "credentialSubject": {
            **flow["credential"]["credentialSubject"],
            "degree": "Forged Degree",
        },
    }
    vp_token = build_signed_presentation(
        tampered_credential,
        nonce=flow["session"]["nonce"],
        domain="testserver",
        holder_did=wallet.holder_did,
        private_key=holder_private_key,
        audience=flow["session"]["clientId"],
    )

    response = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": flow["session"]["sessionId"],
            "vpToken": vp_token,
            "disclosedClaims": flow["claims"],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["holderBindingValid"] is True, response.text
    assert result["signatureValid"] is False
    assert result["finalPolicyResult"] == "REJECTED"


def test_tampered_holder_presentation_proof_fails_direct_post(
    client: TestClient,
) -> None:
    flow = _flow(client)
    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text
    presentation = _create_wallet_presentation(client, flow)
    assert presentation.status_code == 200, presentation.text
    vp_token = presentation.json()["vpToken"]
    vp_token["proof"]["proofValue"] = "zTamperedHolderProofValue"

    response = client.post(
        "/api/v1/oid4vp/response",
        json={
            "sessionId": flow["session"]["sessionId"],
            "vpToken": vp_token,
            "disclosedClaims": flow["claims"],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["holderBindingValid"] is False
    assert result["finalPolicyResult"] == "REJECTED"


def test_replayed_presentation_creation_is_rejected(
    client: TestClient,
) -> None:
    flow = _flow(client)
    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text

    first = _create_wallet_presentation(client, flow)
    assert first.status_code == 200, first.text
    second = _create_wallet_presentation(client, flow)
    assert second.status_code == 409


def test_holder_presentation_does_not_resign_issuer_credential(
    client: TestClient,
) -> None:
    flow = _flow(client)
    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text

    with patch.object(CredentialProofService, "sign_credential") as issuer_signer:
        response = _create_wallet_presentation(client, flow)

    assert response.status_code == 200, response.text
    issuer_signer.assert_not_called()
    embedded = response.json()["vpToken"]["verifiableCredential"][0]
    assert embedded == flow["credential"]


def test_consent_and_presentation_audit_omit_credential_secrets(
    client: TestClient,
) -> None:
    flow = _flow(client)
    consent = _consent(client, flow)
    assert consent.status_code == 200, consent.text
    presentation = _create_wallet_presentation(client, flow)
    assert presentation.status_code == 200, presentation.text

    manager = get_mongo_connection_manager()
    audit_repository = get_audit_event_repository(manager=manager)
    events = audit_repository.list_by_subject(flow["session"]["sessionId"])
    assert events
    for event in events:
        metadata = str(event.metadata).casefold()
        assert "private_key" not in metadata
        assert "d_multibase" not in metadata
        assert "proofvalue" not in metadata
        assert flow["claims"]["degree"].casefold() not in metadata


def test_legacy_reject_consent_and_signer_routes_remain_retired(
    client: TestClient,
) -> None:
    flow = _flow(client)
    session_id = flow["session"]["sessionId"]
    attempts = (
        client.post(
            f"/api/v1/oid4vp/requests/{session_id}/reject",
            json={"holderDid": "did:key:attacker", "reason": "forged denial"},
        ),
        client.post(
            f"/api/v1/oid4vp/requests/{session_id}/consent",
            json={
                "action": "APPROVE",
                "holderDid": "did:key:attacker",
                "approvedCredentials": [flow["credential"]["id"]],
                "approvedClaims": flow["claims"],
            },
        ),
        client.post(
            "/api/v1/oid4vp/presentation",
            json={
                "sessionId": session_id,
                "holderDid": "did:key:attacker",
                "verifiableCredentials": [flow["credential"]],
                "disclosedClaims": flow["claims"],
                "allowUnconsentedTestMode": True,
            },
        ),
    )
    assert [response.status_code for response in attempts] == [410, 410, 410]
    assert all(
        "wallet" in response.json()["error"]["message"].casefold()
        for response in attempts
    )

    status_response = client.get(
        f"/api/v1/oid4vp/requests/{session_id}",
        headers=flow["verifier_headers"],
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "PENDING"
    assert status_response.json()["consentStatus"] == "PENDING"
