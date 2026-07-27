from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_authentication_service
from app.domain.persistence import PersistenceUnavailableError
from app.main import app


def test_mongo_auth_unavailability_returns_sanitized_503() -> None:
    sensitive_uri = (
        "mongodb://identity_app:sensitive-password@private-host/identity"
    )

    class FailingAuthenticationService:
        def authenticate(self, **_credentials: str) -> None:
            raise PersistenceUnavailableError(sensitive_uri)

    app.dependency_overrides[get_authentication_service] = (
        lambda: FailingAuthenticationService()
    )
    try:
        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:
            response = client.post(
                "/api/v1/auth/token",
                json={
                    "username": "issuer@example.test",
                    "password": "not-logged",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "PERSISTENCE_UNAVAILABLE",
        "message": "The persistence service is temporarily unavailable.",
        "details": [],
    }
    assert "sensitive-password" not in response.text
    assert "private-host" not in response.text
