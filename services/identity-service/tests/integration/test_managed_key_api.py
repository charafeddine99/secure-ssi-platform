from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_managed_key_service
from app.main import app
from tests.unit.test_managed_key_service import Runtime, WALLET_ID


PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
}


@pytest.fixture
def managed_key_client() -> Iterator[tuple[TestClient, Runtime]]:
    runtime = Runtime()
    app.dependency_overrides[get_managed_key_service] = (
        lambda: runtime.service
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, runtime
    app.dependency_overrides.clear()


def _headers(client: TestClient, role: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": f"{role}@example.test",
            "password": PASSWORDS[role],
        },
    )
    assert response.status_code == 200
    return {
        "Authorization": f"Bearer {response.json()['accessToken']}"
    }


def test_managed_key_api_creation_read_rotation_and_non_export(
    managed_key_client: tuple[TestClient, Runtime],
) -> None:
    client, _ = managed_key_client
    holder_headers = {
        **_headers(client, "holder"),
        "Idempotency-Key": "api-key-create-0001",
    }
    created = client.post(
        f"/api/v1/wallets/{WALLET_ID}/keys",
        json={},
        headers=holder_headers,
    )

    assert created.status_code == 201, created.text
    body = created.json()
    serialized = created.text.casefold()
    assert body["state"] == "ACTIVE"
    assert body["purpose"] == "PRESENTATION_SIGNING"
    assert "providerkeyreference" not in serialized
    assert "private" not in serialized
    read = client.get(
        f"/api/v1/wallets/{WALLET_ID}/keys/{body['keyId']}",
        headers=_headers(client, "holder"),
    )
    listed = client.get(
        f"/api/v1/wallets/{WALLET_ID}/keys?limit=1",
        headers=_headers(client, "holder"),
    )
    assert read.status_code == 200
    admin_read = client.get(
        f"/api/v1/wallets/{WALLET_ID}/keys/{body['keyId']}",
        headers=_headers(client, "admin"),
    )
    assert admin_read.status_code == 404
    assert listed.status_code == 200
    assert listed.json()["items"][0]["keyId"] == body["keyId"]

    rotated = client.post(
        (
            f"/api/v1/wallets/{WALLET_ID}/keys/"
            f"{body['keyId']}/rotate"
        ),
        json={},
        headers={
            **_headers(client, "holder"),
            "Idempotency-Key": "api-key-rotation-0001",
        },
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["keyVersion"] == 2
    assert rotated.json()["holderDid"] != body["holderDid"]


def test_managed_key_api_rbac_and_non_enumerating_behavior(
    managed_key_client: tuple[TestClient, Runtime],
) -> None:
    client, _ = managed_key_client
    path = f"/api/v1/wallets/{WALLET_ID}/keys"

    for role in ("issuer", "verifier"):
        response = client.post(
            path,
            json={},
            headers={
                **_headers(client, role),
                "Idempotency-Key": f"{role}-forbidden-0001",
            },
        )
        assert response.status_code == 403
    missing_header = client.post(
        path,
        json={},
        headers=_headers(client, "holder"),
    )
    assert missing_header.status_code == 422
    rejected_extra = client.post(
        path,
        json={"privateKey": "forbidden"},
        headers={
            **_headers(client, "holder"),
            "Idempotency-Key": "invalid-body-0001",
        },
    )
    assert rejected_extra.status_code == 422
    missing = client.get(
        (
            f"/api/v1/wallets/{WALLET_ID}/keys/"
            "key_0000000000000099"
        ),
        headers=_headers(client, "holder"),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "MANAGED_KEY_NOT_FOUND"


def test_admin_compromise_requires_elevated_permission_and_reason(
    managed_key_client: tuple[TestClient, Runtime],
) -> None:
    client, _ = managed_key_client
    created = client.post(
        f"/api/v1/wallets/{WALLET_ID}/keys",
        json={},
        headers={
            **_headers(client, "holder"),
            "Idempotency-Key": "api-compromise-create-0001",
        },
    )
    key_id = created.json()["keyId"]
    path = (
        f"/api/v1/wallets/{WALLET_ID}/keys/{key_id}/compromise"
    )

    holder_attempt = client.post(
        path,
        json={"reason": "holder attempted compromise"},
        headers=_headers(client, "holder"),
    )
    admin_attempt = client.post(
        path,
        json={"reason": "administrator confirmed compromise"},
        headers=_headers(client, "admin"),
    )

    assert holder_attempt.status_code == 403
    assert admin_attempt.status_code == 200, admin_attempt.text
    assert admin_attempt.json()["state"] == "COMPROMISED"


def test_openapi_documents_all_managed_key_endpoints() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/wallets/{wallet_id}/keys",
        "/api/v1/wallets/{wallet_id}/keys/{key_id}",
        "/api/v1/wallets/{wallet_id}/keys/{key_id}/rotate",
        "/api/v1/wallets/{wallet_id}/keys/{key_id}/suspend",
        "/api/v1/wallets/{wallet_id}/keys/{key_id}/resume",
        "/api/v1/wallets/{wallet_id}/keys/{key_id}/compromise",
        "/api/v1/wallets/{wallet_id}/keys/{key_id}/revoke",
        (
            "/api/v1/wallets/{wallet_id}/keys/{key_id}/"
            "schedule-destruction"
        ),
        (
            "/api/v1/wallets/{wallet_id}/keys/{key_id}/"
            "cancel-destruction"
        ),
        "/api/v1/wallets/{wallet_id}/keys/{key_id}/reconcile",
    }
    assert expected.issubset(paths)
