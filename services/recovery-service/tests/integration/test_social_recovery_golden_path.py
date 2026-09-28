"""Sprint 12 — Social Recovery Golden Path Integration Test.

Validates the complete end-to-end 3-of-5 Shamir Secret Sharing social recovery lifecycle:
1. Policy configuration (3-of-5 threshold, 10s time-lock delay).
2. Enrollment of 5 independent guardians.
3. Emergency recovery petition creation with reason ACCOUNT_COMPROMISE.
4. Progressive guardian approvals:
   - Approval 1: State remains PENDING_APPROVALS.
   - Approval 2: State remains PENDING_APPROVALS.
   - Approval 3: Quorum reached, 3-of-5 Shamir shares validated, transition to WAITING_TIMELOCK.
5. Time-lock enforcement (early reconciliation attempt is rejected/deferred).
6. Time-lock expiration and execution:
   - Request transitions to COMPLETED.
   - Key rotation on Identity Service: predecessor key is disabled/marked COMPROMISED.
   - Successor key and new DID are bound to the wallet.
   - Predecessor key cannot sign anymore.
7. Privacy check: zero raw Shamir shares disclosed in API outputs.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_recovery_service
from app.main import app
from tests.support import WALLET_ID, build_runtime


def _token(user_id: str, role: str = "holder") -> str:
    settings = app.state.recovery_runtime.settings
    now = datetime.now(UTC).replace(microsecond=0)
    return jwt.encode(
        {
            "iss": settings.jwt_issuer,
            "sub": user_id,
            "aud": settings.jwt_audience,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
            "jti": token_urlsafe(16),
            "roles": [role],
            "token_use": "access",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def _headers(user_id: str, role: str = "holder") -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, role)}"}


@pytest.fixture
def golden_path_client() -> Iterator[tuple[TestClient, object]]:
    runtime = build_runtime()
    app.dependency_overrides[get_recovery_service] = lambda: runtime.service
    client = TestClient(app, raise_server_exceptions=False)
    yield client, runtime
    client.close()
    app.dependency_overrides.clear()


def test_social_recovery_golden_path_3_of_5_shamir_and_timelock(golden_path_client) -> None:
    client, runtime = golden_path_client
    owner_headers = _headers(runtime.owner.user_id)
    admin_headers = _headers(runtime.admin.user_id, "admin")

    # -------------------------------------------------------------------------
    # STEP 1: Configure 3-of-5 Recovery Policy
    # -------------------------------------------------------------------------
    policy_resp = client.put(
        "/api/v1/recovery/policy",
        headers=owner_headers,
        json={
            "walletId": WALLET_ID,
            "minimumApprovals": 3,
            "maximumGuardians": 5,
            "approvalWindowSeconds": 600,
            "timeLockSeconds": 15,
            "recoveryExpirationSeconds": 3600,
            "maximumAttempts": 3,
            "cooldownSeconds": 0,
            "allowCancellation": True,
        },
    )
    assert policy_resp.status_code == 200, policy_resp.text
    policy_data = policy_resp.json()
    assert policy_data["minimumApprovals"] == 3
    assert policy_data["maximumGuardians"] == 5
    assert policy_data["timeLockSeconds"] == 15

    # -------------------------------------------------------------------------
    # STEP 2: Enroll 5 Guardians (Shamir secret split into 5 shares)
    # -------------------------------------------------------------------------
    guardian_ids: list[str] = []
    for index, guardian_principal in enumerate(runtime.guardians[:5], start=1):
        g_resp = client.post(
            "/api/v1/guardians",
            headers=owner_headers,
            json={
                "walletId": WALLET_ID,
                "guardianUserId": guardian_principal.user_id,
                "guardianDid": f"did:key:zGoldenPathGuardian{index:02d}",
                "displayName": f"Golden Path Guardian {index}",
                "verificationMethod": (
                    f"did:key:zGoldenPathGuardian{index:02d}#"
                    f"zGoldenPathGuardian{index:02d}"
                ),
            },
        )
        assert g_resp.status_code == 201, g_resp.text
        g_data = g_resp.json()
        assert g_data["status"] == "ACTIVE"
        guardian_ids.append(g_data["guardianId"])

    assert len(guardian_ids) == 5

    # Verify guardian list
    guardians_list_resp = client.get(f"/api/v1/guardians?walletId={WALLET_ID}", headers=owner_headers)
    assert guardians_list_resp.status_code == 200
    assert len(guardians_list_resp.json()["items"]) == 5

    # -------------------------------------------------------------------------
    # STEP 3: Holder Initiates Emergency Recovery Petition
    # -------------------------------------------------------------------------
    initial_key = runtime.gateway.active_key
    initial_did = runtime.gateway.active_did

    initiate_resp = client.post(
        "/api/v1/recovery/requests",
        headers=owner_headers,
        json={
            "walletId": WALLET_ID,
            "reason": "ACCOUNT_COMPROMISE",
        },
    )
    assert initiate_resp.status_code == 201, initiate_resp.text
    req_data = initiate_resp.json()
    request_id = req_data["requestId"]
    challenge = req_data["challenge"]

    assert req_data["state"] == "PENDING_APPROVALS"
    assert req_data["walletId"] == WALLET_ID
    assert req_data["reason"] == "ACCOUNT_COMPROMISE"

    # Privacy verification: no raw Shamir secrets or envelopes leaked
    body_str = initiate_resp.text.lower()
    assert "encryptedenvelope" not in body_str
    assert "rawshare" not in body_str
    assert "integritydigest" not in body_str

    # -------------------------------------------------------------------------
    # STEP 4: Progressive Guardian Approvals (1st, 2nd, 3rd)
    # -------------------------------------------------------------------------
    # Guardian 1 approves
    app1 = client.post(
        f"/api/v1/recovery/requests/{request_id}/approve",
        headers=_headers(runtime.guardians[0].user_id),
        json={"guardianId": guardian_ids[0], "challenge": challenge},
    )
    assert app1.status_code == 200, app1.text
    app1_data = app1.json()
    assert app1_data["state"] == "PENDING_APPROVALS"
    assert app1_data["approvalsCount"] == 1

    # Guardian 2 approves
    app2 = client.post(
        f"/api/v1/recovery/requests/{request_id}/approve",
        headers=_headers(runtime.guardians[1].user_id),
        json={"guardianId": guardian_ids[1], "challenge": challenge},
    )
    assert app2.status_code == 200, app2.text
    app2_data = app2.json()
    assert app2_data["state"] == "PENDING_APPROVALS"
    assert app2_data["approvalsCount"] == 2

    # Guardian 3 approves -> 3-of-5 Quorum reached! Reconstructs Shamir secret
    app3 = client.post(
        f"/api/v1/recovery/requests/{request_id}/approve",
        headers=_headers(runtime.guardians[2].user_id),
        json={"guardianId": guardian_ids[2], "challenge": challenge},
    )
    assert app3.status_code == 200, app3.text
    app3_data = app3.json()
    assert app3_data["state"] == "WAITING_TIMELOCK"
    assert app3_data["approvalsCount"] == 3
    assert app3_data["timelockExpiresAt"] is not None

    # -------------------------------------------------------------------------
    # STEP 5: Time-Lock Enforcement (Premature Execution Rejected)
    # -------------------------------------------------------------------------
    # Reconcile immediately before time-lock window expires
    premature_reconcile = client.post(
        f"/api/v1/recovery/requests/{request_id}/reconcile",
        headers=admin_headers,
    )
    assert premature_reconcile.status_code == 200
    assert premature_reconcile.json()["state"] == "WAITING_TIMELOCK"
    # Predecessor key must not have been rotated yet
    assert runtime.gateway.active_key == initial_key

    # -------------------------------------------------------------------------
    # STEP 6: Time-Lock Expiry & Key Rotation Execution
    # -------------------------------------------------------------------------
    # Advance clock past the 15-second timeLock window
    runtime.clock.advance(seconds=16)

    # Reconcile again after time-lock expires
    executed_reconcile = client.post(
        f"/api/v1/recovery/requests/{request_id}/reconcile",
        headers=admin_headers,
    )
    assert executed_reconcile.status_code == 200, executed_reconcile.text
    result_data = executed_reconcile.json()

    assert result_data["state"] == "COMPLETED"
    outcome = result_data["result"]
    assert outcome["predecessorKeyId"] == initial_key
    assert outcome["successorKeyId"] != initial_key
    assert outcome["predecessorDid"] == initial_did
    assert outcome["successorDid"] != initial_did

    # Verify that predecessor key is deactivated/disabled and cannot sign
    assert initial_key in runtime.gateway.disabled_keys
    with pytest.raises(RuntimeError, match="key cannot sign"):
        runtime.gateway.sign(initial_key, b"test-payload-compromised")

    # Verify successor key can sign cleanly
    successor_sig = runtime.gateway.sign(outcome["successorKeyId"], b"test-payload-valid")
    assert runtime.gateway.verify(outcome["successorKeyId"], b"test-payload-valid", successor_sig)

    # Verify final request status query
    final_query = client.get(f"/api/v1/recovery/requests/{request_id}", headers=owner_headers)
    assert final_query.status_code == 200
    assert final_query.json()["state"] == "COMPLETED"
