from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_current_principal
from app.domain.auth import AuthenticatedPrincipal, User
from app.domain.permissions import Role
from app.main import app


def _holder_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": "holder@example.test",
            "password": "Holder-Prototype-2026!",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_holder_activity_is_wallet_owner_scoped_and_minimized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(app) as client:
        holder_headers = _holder_headers(client)
        created = client.post("/api/v1/wallets", json={}, headers=holder_headers)
        assert created.status_code == 201, created.text
        wallet_id = created.json()["walletId"]
        second = client.post("/api/v1/wallets", json={}, headers=holder_headers)
        assert second.status_code == 201, second.text
        second_wallet_id = second.json()["walletId"]
        path = f"/api/v1/wallets/{wallet_id}/activity?limit=10&offset=0"

        unauthenticated = client.get(
            f"/api/v1/wallets/{wallet_id}/activity"
        )
        assert unauthenticated.status_code == 401

        own = client.get(path, headers=holder_headers)
        assert own.status_code == 200, own.text
        payload = own.json()
        assert payload["walletId"] == wallet_id
        assert any(item["eventType"] == "WALLET_CREATED" for item in payload["items"])
        assert all(
            item["subjectId"] != second_wallet_id for item in payload["items"]
        )
        assert all("metadata" not in item for item in payload["items"])

        other_holder = AuthenticatedPrincipal.from_user(
            User(
                id="usr_unrelated_holder",
                username="unrelated-holder@example.test",
                display_name="Unrelated Holder",
                roles=(Role.HOLDER,),
            ),
            authentication_source="test",
        )
        monkeypatch.setitem(
            app.dependency_overrides,
            get_current_principal,
            lambda: other_holder,
        )
        foreign = client.get(
            f"/api/v1/wallets/{wallet_id}/activity"
        )
        assert foreign.status_code == 404
