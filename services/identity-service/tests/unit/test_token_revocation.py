"""Test Token Revocation Store and Authentication Service Blacklist."""

import pytest
from datetime import datetime, timezone, timedelta
from app.infrastructure.auth.token_revocation import TokenRevocationStore, get_token_revocation_store
from app.domain.exceptions import AccessTokenRevokedError
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def store():
    s = TokenRevocationStore()
    return s


def test_token_revocation_store_basic(store: TokenRevocationStore):
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)
    jti = "test-jti-12345"

    assert not store.is_revoked(jti)
    store.revoke_token(jti, expires_at=exp, reason="logout")
    assert store.is_revoked(jti)
    assert store.count() == 1


def test_token_revocation_store_subject(store: TokenRevocationStore):
    jti = "test-jti-abc"
    user_id = "user-quarantined-999"

    assert not store.is_revoked(jti, subject=user_id)
    store.revoke_subject(user_id, reason="fraud_quarantine")
    assert store.is_revoked(jti, subject=user_id)

    store.reinstate_subject(user_id)
    assert not store.is_revoked(jti, subject=user_id)


def test_token_revocation_store_expired_pruning(store: TokenRevocationStore):
    now = datetime.now(timezone.utc)
    expired_time = now - timedelta(seconds=10)
    jti = "expired-jti"

    store.revoke_token(jti, expires_at=expired_time, reason="test")
    # Natural expiry prunes from blacklist
    assert not store.is_revoked(jti)


def test_token_revocation_store_uses_injected_clock():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    store = TokenRevocationStore(clock=lambda: now)

    store.revoke_token("fixed-clock-jti", expires_at=now + timedelta(minutes=1))

    assert store.is_revoked("fixed-clock-jti")


def test_token_revocation_api_endpoint():
    get_token_revocation_store().clear()
    client = TestClient(app)

    # 1. Login to get token
    login_resp = client.post(
        "/api/v1/auth/token",
        json={"username": "admin@example.test", "password": "Admin-Prototype-2026!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json().get("accessToken") or login_resp.json().get("access_token")

    # 2. Access /auth/me -> 200 OK
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200

    # 3. Revoke via POST /api/v1/auth/revoke
    revoke_resp = client.post(
        "/api/v1/auth/revoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "user_logout"},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "SUCCESS"

    # 4. Access /auth/me with revoked token -> 401 Unauthorized with ACCESS_TOKEN_REVOKED
    blocked_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert blocked_resp.status_code == 401
    assert blocked_resp.json()["error"]["code"] == "ACCESS_TOKEN_REVOKED"
