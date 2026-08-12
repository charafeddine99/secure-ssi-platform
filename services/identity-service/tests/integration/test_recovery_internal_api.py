from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_holder_wallet_repository,
    get_managed_key_service,
)
from app.config.recovery_grant_settings import load_recovery_grant_settings
from app.domain.managed_key import ManagedKeyState
from app.main import app
from tests.unit.test_managed_key_service import OWNER, WALLET_ID, Runtime


REQUEST_ID = "recovery_0000000000000001"


def _grant(*, scope: str, wallet_id: str = WALLET_ID, owner: str = OWNER) -> str:
    settings = load_recovery_grant_settings({})
    now = datetime.now(UTC).replace(microsecond=0)
    return jwt.encode(
        {
            "iss": settings.issuer,
            "sub": owner,
            "aud": settings.audience,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=60)).timestamp()),
            "jti": f"grant-{scope}",
            "scope": scope,
            "wallet_id": wallet_id,
            "request_id": REQUEST_ID,
        },
        settings.secret,
        algorithm="HS256",
    )


@pytest.fixture
def internal_client() -> Iterator[tuple[TestClient, Runtime]]:
    runtime = Runtime()
    runtime.create()
    app.dependency_overrides[get_holder_wallet_repository] = lambda: runtime.wallets
    app.dependency_overrides[get_managed_key_service] = lambda: runtime.service
    client = TestClient(app, raise_server_exceptions=False)
    yield client, runtime
    client.close()
    app.dependency_overrides.clear()


def test_internal_recovery_ownership_and_key_rotation_are_bound_and_idempotent(
    internal_client: tuple[TestClient, Runtime],
) -> None:
    client, runtime = internal_client
    ownership = client.get(
        f"/internal/v1/recovery/wallets/{WALLET_ID}/owners/{OWNER}",
        headers={
            "Authorization": f"Bearer {_grant(scope='wallet:ownership:read')}"
        },
    )
    rotated = client.post(
        "/internal/v1/recovery/key-rotation",
        headers={
            "Authorization": f"Bearer {_grant(scope='managed-key:recover')}",
            "Idempotency-Key": f"recovery:{REQUEST_ID}",
        },
        json={
            "recoveryRequestId": REQUEST_ID,
            "walletId": WALLET_ID,
            "ownerUserId": OWNER,
            "reason": "ACCOUNT_COMPROMISE",
        },
    )
    repeated = client.post(
        "/internal/v1/recovery/key-rotation",
        headers={
            "Authorization": f"Bearer {_grant(scope='managed-key:recover')}",
            "Idempotency-Key": f"recovery:{REQUEST_ID}",
        },
        json={
            "recoveryRequestId": REQUEST_ID,
            "walletId": WALLET_ID,
            "ownerUserId": OWNER,
            "reason": "ACCOUNT_COMPROMISE",
        },
    )

    assert ownership.status_code == 204
    assert rotated.status_code == repeated.status_code == 200
    assert rotated.json() == repeated.json()
    assert rotated.json()["predecessorDid"] != rotated.json()["successorDid"]
    predecessor = runtime.keys.get(rotated.json()["predecessorKeyId"])
    assert predecessor is not None
    assert predecessor.state is ManagedKeyState.COMPROMISED
    assert not any(path.startswith("/internal") for path in app.openapi()["paths"])


def test_internal_recovery_rejects_wrong_scope_binding_and_idempotency(
    internal_client: tuple[TestClient, Runtime],
) -> None:
    client, _ = internal_client
    wrong_scope = client.post(
        "/internal/v1/recovery/key-rotation",
        headers={
            "Authorization": f"Bearer {_grant(scope='wallet:ownership:read')}",
            "Idempotency-Key": f"recovery:{REQUEST_ID}",
        },
        json={
            "recoveryRequestId": REQUEST_ID,
            "walletId": WALLET_ID,
            "ownerUserId": OWNER,
            "reason": "KEY_LOSS",
        },
    )
    wrong_idempotency = client.post(
        "/internal/v1/recovery/key-rotation",
        headers={
            "Authorization": f"Bearer {_grant(scope='managed-key:recover')}",
            "Idempotency-Key": "recovery:another-request-id",
        },
        json={
            "recoveryRequestId": REQUEST_ID,
            "walletId": WALLET_ID,
            "ownerUserId": OWNER,
            "reason": "KEY_LOSS",
        },
    )
    foreign = client.get(
        "/internal/v1/recovery/wallets/wallet_foreignabcdefghij/owners/"
        f"{OWNER}",
        headers={
            "Authorization": f"Bearer {_grant(scope='wallet:ownership:read')}"
        },
    )
    assert wrong_scope.status_code == 401
    assert wrong_idempotency.status_code == 409
    assert foreign.status_code == 401
