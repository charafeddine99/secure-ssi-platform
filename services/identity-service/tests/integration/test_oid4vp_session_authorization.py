from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_current_principal
from app.application.services.oid4vp_service import Oid4vpService
from app.domain.auth import AuthenticatedPrincipal, User
from app.domain.oid4vp import SessionNotFoundError, VerificationSession
from app.domain.permissions import Role
from app.main import app


PASSWORDS = {
    "verifier": "Verifier-Prototype-2026!",
    "holder": "Holder-Prototype-2026!",
}


def _headers(client: TestClient, role: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        json={"username": f"{role}@example.test", "password": PASSWORDS[role]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _new_session(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/oid4vp/requests",
        json={
            "purpose": "Verify an affiliation",
            "requestedCredentialTypes": ["UniversityAffiliationCredential"],
            "requestedFields": ["degree"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["sessionId"]


def test_verifier_result_poll_requires_authentication_and_exact_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(app) as client:
        owner_headers = _headers(client, "verifier")
        session_id = _new_session(client, owner_headers)

        unauthenticated = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        assert unauthenticated.status_code == 401

        owned = client.get(
            f"/api/v1/oid4vp/requests/{session_id}", headers=owner_headers
        )
        assert owned.status_code == 200, owned.text
        assert owned.json()["sessionId"] == session_id
        assert owned.json()["status"] == "PENDING"

        other_verifier = AuthenticatedPrincipal.from_user(
            User(
                id="usr_other_verifier",
                username="another-verifier@example.test",
                display_name="Another Verifier",
                roles=(Role.VERIFIER,),
            ),
            authentication_source="test",
        )
        monkeypatch.setitem(
            app.dependency_overrides,
            get_current_principal,
            lambda: other_verifier,
        )
        foreign = client.get(f"/api/v1/oid4vp/requests/{session_id}")
        guessed = client.get(
            "/api/v1/oid4vp/requests/session_000000000000000000000000"
        )
        assert foreign.status_code == 404
        assert guessed.status_code == 404
        assert (
            foreign.json()["error"]["message"]
            == guessed.json()["error"]["message"]
        )


def test_holder_gets_only_authenticated_protocol_request_context() -> None:
    with TestClient(app) as client:
        verifier_headers = _headers(client, "verifier")
        holder_headers = _headers(client, "holder")
        session_id = _new_session(client, verifier_headers)
        path = f"/api/v1/oid4vp/requests/{session_id}/holder-request"

        unauthenticated = client.get(path)
        assert unauthenticated.status_code == 401

        response = client.get(path, headers=holder_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["sessionId"] == session_id
        assert payload["purpose"] == "Verify an affiliation"
        assert payload["status"] == "PENDING"
        assert "verificationResult" not in payload
        assert "disclosedClaims" not in payload
        assert "rejectionReason" not in payload

        wrong_role = client.get(path, headers=verifier_headers)
        assert wrong_role.status_code == 403


def test_holder_dcql_evaluation_requires_holder_authentication() -> None:
    with TestClient(app) as client:
        verifier_headers = _headers(client, "verifier")
        holder_headers = _headers(client, "holder")
        session_id = _new_session(client, verifier_headers)
        path = f"/api/v1/oid4vp/requests/{session_id}/evaluate-dcql"

        unauthenticated = client.post(path, json={"candidateCredentials": []})
        assert unauthenticated.status_code == 401

        evaluated = client.post(
            path,
            json={"candidateCredentials": []},
            headers=holder_headers,
        )
        assert evaluated.status_code == 200, evaluated.text
        assert evaluated.json()["isSatisfied"] is False


def test_session_without_persisted_owner_fails_closed() -> None:
    now = datetime.now(UTC)
    legacy_session = VerificationSession(
        id="000000000000000000000001",
        session_id="session_000000000000000000000001",
        verifier_did="did:web:verifier.example",
        client_id="https://verifier.example",
        response_uri="https://verifier.example/response",
        nonce="0123456789abcdef",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
        owner_user_id=None,
    )
    repository = Mock()
    repository.get_by_session_id.return_value = legacy_session
    service = Oid4vpService(
        session_repository=repository,
        credential_repository=Mock(),
        audit_repository=Mock(),
        verifier_presentation_service=Mock(),
    )

    with pytest.raises(SessionNotFoundError):
        service.get_session_for_owner(
            legacy_session.session_id,
            owner_user_id="usr_local_verifier",
        )
