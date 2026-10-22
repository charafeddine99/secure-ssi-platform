from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _token(client: TestClient, role: str) -> str:
    passwords = {
        "verifier": "Verifier-Prototype-2026!",
        "holder": "Holder-Prototype-2026!",
    }
    response = client.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": passwords[role]},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


def test_legacy_oid4vp_write_and_sign_routes_fail_closed() -> None:
    with TestClient(app) as client:
        verifier_token = _token(client, "verifier")
        session_response = client.post(
            "/api/v1/oid4vp/requests",
            json={
                "purpose": "Security regression test",
                "requestedCredentialTypes": ["UniversityAffiliationCredential"],
                "requestedFields": ["degree"],
            },
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["sessionId"]

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
                    "approvedCredentials": ["attacker-controlled"],
                    "approvedClaims": {"degree": "forged"},
                },
            ),
            client.post(
                "/api/v1/oid4vp/presentation",
                json={
                    "sessionId": session_id,
                    "holderDid": "did:key:attacker",
                    "verifiableCredentials": [],
                    "allowUnconsentedTestMode": True,
                },
            ),
        )

        assert [response.status_code for response in attempts] == [410, 410, 410]
        assert all(
            "wallet" in response.json()["error"]["message"].lower()
            for response in attempts
        )

        current = client.get(
            f"/api/v1/oid4vp/requests/{session_id}",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert current.status_code == 200
        assert current.json()["status"] == "PENDING"
        assert current.json()["consentStatus"] == "PENDING"


def test_wallet_bound_oid4vp_write_and_sign_routes_require_authentication() -> None:
    with TestClient(app) as client:
        verifier_token = _token(client, "verifier")
        session_response = client.post(
            "/api/v1/oid4vp/requests",
            json={
                "purpose": "Authentication regression test",
                "requestedCredentialTypes": ["UniversityAffiliationCredential"],
                "requestedFields": ["degree"],
            },
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["sessionId"]

        consent = client.post(
            f"/api/v1/oid4vp/requests/{session_id}/wallet-consent",
            json={
                "walletId": "not-owned",
                "holderDid": "did:key:attacker",
                "action": "REJECT",
            },
        )
        presentation = client.post(
            "/api/v1/oid4vp/wallet-presentation",
            json={
                "sessionId": session_id,
                "walletId": "not-owned",
                "credentialIds": ["credential"],
                "disclosedClaims": {},
            },
        )

        assert consent.status_code == 401
        assert presentation.status_code == 401

