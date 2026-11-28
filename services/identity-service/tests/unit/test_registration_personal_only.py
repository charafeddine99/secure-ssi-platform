"""Public sign-up gives no organization or platform power; issuer/verifier come from organizations."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import registration
from app.api.v1.registration import RegisterRequest, _legacy_role_applications_enabled, register_account


def settings(environment: str) -> SimpleNamespace:
    return SimpleNamespace(environment=environment, user_provider="mongodb")


def test_legacy_role_applications_default_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IDENTITY_LEGACY_ROLE_APPLICATIONS_ENABLED", raising=False)
    assert _legacy_role_applications_enabled(settings("development")) is True
    assert _legacy_role_applications_enabled(settings("production")) is False
    monkeypatch.setenv("IDENTITY_LEGACY_ROLE_APPLICATIONS_ENABLED", "false")
    assert _legacy_role_applications_enabled(settings("development")) is False


@pytest.mark.parametrize("role", ["issuer", "verifier"])
def test_issuer_and_verifier_sign_up_is_refused_when_off(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    monkeypatch.setenv("IDENTITY_LEGACY_ROLE_APPLICATIONS_ENABLED", "false")
    monkeypatch.setenv("IDENTITY_SELF_REGISTRATION_ENABLED", "true")
    payload = RegisterRequest(email="new@example.test", display_name="New Person", password="long-enough-passphrase-2026",
                              role=role, organization="Example Org", purpose="Issue things")
    with pytest.raises(HTTPException) as refused:
        register_account(payload, settings=settings("production"), users=None, hasher=None, manager=None, audit_events=None)
    assert refused.value.status_code == 403
    assert "Organizations" in refused.value.detail


def test_admin_still_needs_an_invitation() -> None:
    assert registration._MESSAGES["admin"].startswith("If the invitation is valid")
