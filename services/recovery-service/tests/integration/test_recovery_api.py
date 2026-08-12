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
            "exp": int((now + timedelta(minutes=5)).timestamp()),
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
def api() -> Iterator[tuple[TestClient, object]]:
    runtime = build_runtime()
    app.dependency_overrides[get_recovery_service] = lambda: runtime.service
    client = TestClient(app, raise_server_exceptions=False)
    yield client, runtime
    client.close()
    app.dependency_overrides.clear()


def _configure(client: TestClient, runtime, *, time_lock: int = 10) -> list[str]:
    owner_headers = _headers(runtime.owner.user_id)
    policy = client.put(
        "/api/v1/recovery/policy",
        headers=owner_headers,
        json={
            "walletId": WALLET_ID,
            "minimumApprovals": 3,
            "maximumGuardians": 5,
            "approvalWindowSeconds": 300,
            "timeLockSeconds": time_lock,
            "recoveryExpirationSeconds": 1200,
            "maximumAttempts": 3,
            "cooldownSeconds": 0,
            "allowCancellation": True,
        },
    )
    assert policy.status_code == 200, policy.text
    guardian_ids = []
    for index, guardian in enumerate(runtime.guardians[:5], start=1):
        response = client.post(
            "/api/v1/guardians",
            headers=owner_headers,
            json={
                "walletId": WALLET_ID,
                "guardianUserId": guardian.user_id,
                "guardianDid": f"did:key:zApiGuardianRecovery{index:02d}",
                "displayName": f"API Guardian {index}",
                "verificationMethod": (
                    f"did:key:zApiGuardianRecovery{index:02d}#"
                    f"zApiGuardianRecovery{index:02d}"
                ),
            },
        )
        assert response.status_code == 201, response.text
        guardian_ids.append(response.json()["guardianId"])
    return guardian_ids


def test_guardian_crud_policy_and_strict_openapi(api) -> None:
    client, runtime = api
    guardian_ids = _configure(client, runtime)
    headers = _headers(runtime.owner.user_id)

    listed = client.get(
        f"/api/v1/guardians?walletId={WALLET_ID}", headers=headers
    )
    read = client.get(f"/api/v1/guardians/{guardian_ids[0]}", headers=headers)
    patched = client.patch(
        f"/api/v1/guardians/{guardian_ids[0]}",
        headers=headers,
        json={"status": "SUSPENDED"},
    )
    resumed = client.patch(
        f"/api/v1/guardians/{guardian_ids[0]}",
        headers=headers,
        json={"status": "ACTIVE"},
    )
    removed = client.delete(
        f"/api/v1/guardians/{guardian_ids[4]}", headers=headers
    )
    policy = client.get(
        f"/api/v1/recovery/policy?walletId={WALLET_ID}", headers=headers
    )
    extra = client.post(
        "/api/v1/guardians",
        headers=headers,
        json={
            "walletId": WALLET_ID,
            "guardianUserId": "usr_extra_guardian",
            "guardianDid": "did:key:zExtraApiGuardian",
            "displayName": "Extra",
            "verificationMethod": "did:key:zExtraApiGuardian#zExtraApiGuardian",
            "rawShare": "forbidden",
        },
    )

    assert listed.status_code == 200 and len(listed.json()["items"]) == 5
    assert read.status_code == 200
    assert patched.json()["status"] == "SUSPENDED"
    assert resumed.json()["status"] == "ACTIVE"
    assert removed.json()["status"] == "REMOVED"
    assert policy.json()["minimumApprovals"] == 3
    assert extra.status_code == 422
    assert set(extra.json()) == {"code", "message", "requestId"}
    assert "detail" not in extra.json()
    schema = client.get("/openapi.json").json()
    assert "/api/v1/recovery/requests/{request_id}/approve" in schema["paths"]
    assert not any("share" in path.casefold() for path in schema["paths"])


def test_recovery_api_full_flow_and_no_share_disclosure(api) -> None:
    client, runtime = api
    guardian_ids = _configure(client, runtime, time_lock=10)
    created = client.post(
        "/api/v1/recovery/requests",
        headers=_headers(runtime.owner.user_id),
        json={"walletId": WALLET_ID, "reason": "ACCOUNT_COMPROMISE"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    serialized = created.text.casefold()
    assert body["state"] == "PENDING_APPROVALS"
    assert "encryptedenvelope" not in serialized
    assert "integritydigest" not in serialized
    request_id = body["requestId"]
    for index in range(3):
        response = client.post(
            f"/api/v1/recovery/requests/{request_id}/approve",
            headers=_headers(runtime.guardians[index].user_id),
            json={
                "guardianId": guardian_ids[index],
                "challenge": body["challenge"],
            },
        )
        assert response.status_code == 200, response.text
    waiting = client.get(
        f"/api/v1/recovery/requests/{request_id}",
        headers=_headers(runtime.owner.user_id),
    )
    assert waiting.json()["state"] == "WAITING_TIMELOCK"
    early = client.post(
        f"/api/v1/recovery/requests/{request_id}/reconcile",
        headers=_headers(runtime.admin.user_id, "admin"),
    )
    assert early.json()["state"] == "WAITING_TIMELOCK"
    runtime.clock.advance(seconds=10)
    completed = client.post(
        f"/api/v1/recovery/requests/{request_id}/reconcile",
        headers=_headers(runtime.admin.user_id, "admin"),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["state"] == "COMPLETED"
    assert completed.json()["result"]["predecessorDid"] != (
        completed.json()["result"]["successorDid"]
    )


def test_api_rbac_non_enumeration_duplicate_decision_and_cancellation(api) -> None:
    client, runtime = api
    guardian_ids = _configure(client, runtime)
    owner_headers = _headers(runtime.owner.user_id)
    created = client.post(
        "/api/v1/recovery/requests",
        headers=owner_headers,
        json={"walletId": WALLET_ID, "reason": "LOST_ACCESS"},
    ).json()
    path = f"/api/v1/recovery/requests/{created['requestId']}"
    first = client.post(
        path + "/approve",
        headers=_headers(runtime.guardians[0].user_id),
        json={
            "guardianId": guardian_ids[0],
            "challenge": created["challenge"],
        },
    )
    duplicate = client.post(
        path + "/approve",
        headers=_headers(runtime.guardians[0].user_id),
        json={
            "guardianId": guardian_ids[0],
            "challenge": created["challenge"],
        },
    )
    foreign = client.get(path, headers=_headers("usr_foreign_holder"))
    verifier = client.get(path, headers=_headers("usr_verifier", "verifier"))
    issuer = client.post(
        "/api/v1/recovery/requests",
        headers=_headers("usr_issuer", "issuer"),
        json={"walletId": WALLET_ID, "reason": "KEY_LOSS"},
    )
    cancelled = client.post(path + "/cancel", headers=owner_headers)
    late = client.post(
        path + "/approve",
        headers=_headers(runtime.guardians[1].user_id),
        json={
            "guardianId": guardian_ids[1],
            "challenge": created["challenge"],
        },
    )

    assert first.status_code == duplicate.status_code == 200
    assert first.json()["approval"] == duplicate.json()["approval"]
    assert foreign.status_code == 404
    assert verifier.status_code == issuer.status_code == 403
    assert cancelled.json()["state"] == "CANCELLED"
    assert late.status_code == 409


def test_authentication_and_invalid_policy_errors(api) -> None:
    client, runtime = api
    missing = client.get(f"/api/v1/recovery/policy?walletId={WALLET_ID}")
    malformed = client.get(
        f"/api/v1/recovery/policy?walletId={WALLET_ID}",
        headers={"Authorization": "Bearer malformed"},
    )
    invalid = client.put(
        "/api/v1/recovery/policy",
        headers=_headers(runtime.owner.user_id),
        json={
            "walletId": WALLET_ID,
            "minimumApprovals": 4,
            "maximumGuardians": 3,
            "approvalWindowSeconds": 300,
            "timeLockSeconds": 10,
            "recoveryExpirationSeconds": 1200,
            "maximumAttempts": 3,
            "cooldownSeconds": 0,
            "allowCancellation": True,
        },
    )
    invalid_request_id = client.get(
        f"/api/v1/recovery/policy?walletId={WALLET_ID}",
        headers={
            **_headers(runtime.owner.user_id),
            "X-Request-ID": "x" * 256,
        },
    )
    assert missing.status_code == malformed.status_code == 401
    assert invalid.status_code == 422
    assert set(missing.json()) == {"code", "message", "requestId"}
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert invalid_request_id.headers["X-Request-ID"].startswith("req_")
