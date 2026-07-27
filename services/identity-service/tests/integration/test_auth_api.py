import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_authentication_service,
    get_clock,
    get_credential_api_service,
    get_credential_issuance_repository,
    get_status_list_entry_repository,
)
from app.application.services.authentication_service import AuthenticationService
from app.config.auth_settings import AuthSettings
from app.domain.auth import AuthenticatedPrincipal, User
from app.domain.permissions import Role
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.auth.jwt_access_token_service import (
    JwtAccessTokenService,
)
from app.infrastructure.auth.local_synthetic_user_provider import (
    LocalAuthenticationRecord,
    LocalSyntheticUserProvider,
)
from app.infrastructure.persistence.issuance_repository import (
    MongoCredentialIssuanceRepository,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
)
from app.main import app
from tests.support.fake_mongo import FakeDatabase


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
UNSIGNED_PATH = FIXTURE_ROOT / "unsigned-university-affiliation.vc.json"
SIGNED_PATH = FIXTURE_ROOT / "valid-signed-university-affiliation.vc.json"
FIXED_TIME = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
TEST_SECRET = "integration-test-jwt-secret-at-least-thirty-two-bytes"
OTHER_SECRET = "integration-other-jwt-secret-at-least-thirty-two-bytes"
PASSWORDS = {
    "admin": "Admin-Prototype-2026!",
    "issuer": "Issuer-Prototype-2026!",
    "verifier": "Verifier-Prototype-2026!",
    "disabled": "Disabled-Prototype-2026!",
}


@dataclass
class AuthContext:
    settings: AuthSettings
    provider: LocalSyntheticUserProvider
    token_service: JwtAccessTokenService
    service: AuthenticationService


@pytest.fixture
def auth_context() -> AuthContext:
    settings = AuthSettings(
        enabled=True,
        jwt_issuer="test-secure-ssi-identity",
        jwt_audience="identity-service",
        access_token_lifetime_seconds=900,
        jwt_algorithm="HS256",
        jwt_secret=TEST_SECRET,
        local_fixture_users_enabled=True,
        clock_skew_seconds=10,
        environment="test",
    )
    provider = LocalSyntheticUserProvider.default()
    token_service = JwtAccessTokenService(settings)
    service = AuthenticationService(
        user_provider=provider,
        password_hasher=Argon2PasswordHasher(),
        access_token_service=token_service,
        clock=lambda: FIXED_TIME,
        jti_generator=lambda: "fixed-integration-jti",
    )
    return AuthContext(
        settings=settings,
        provider=provider,
        token_service=token_service,
        service=service,
    )


@pytest.fixture
def client(auth_context: AuthContext) -> TestClient:
    database = FakeDatabase()
    app.dependency_overrides[get_authentication_service] = (
        lambda: auth_context.service
    )
    app.dependency_overrides[get_clock] = lambda: (lambda: FIXED_TIME)
    app.dependency_overrides[
        get_credential_issuance_repository
    ] = lambda: MongoCredentialIssuanceRepository(
        database["credentials"]  # type: ignore[arg-type]
    )
    app.dependency_overrides[
        get_status_list_entry_repository
    ] = lambda: MongoCredentialStatusEntryRepository(
        database["credential_status_entries"],  # type: ignore[arg-type]
        database["credentials"],  # type: ignore[arg-type]
    )
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def login(client: TestClient, role: str) -> tuple[str, dict[str, Any]]:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": f"{role}@example.test",
            "password": PASSWORDS[role],
        },
    )
    assert response.status_code == 200
    return response.json()["accessToken"], response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def principal_for(
    provider: LocalSyntheticUserProvider,
    username: str,
) -> AuthenticatedPrincipal:
    record = provider.find_by_username(username)
    assert record is not None
    return AuthenticatedPrincipal.from_user(
        record.user,
        authentication_source=provider.authentication_source,
    )


def issue_for(
    auth_context: AuthContext,
    principal: AuthenticatedPrincipal,
    *,
    issued_at: datetime = FIXED_TIME,
    jwt_id: str = "custom-test-jti",
) -> str:
    return auth_context.token_service.issue_access_token(
        principal,
        issued_at=issued_at,
        jwt_id=jwt_id,
    )


def raw_payload(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        options={"verify_signature": False},
        algorithms=["HS256"],
    )


def encode_payload(
    payload: dict[str, Any],
    *,
    secret: str = TEST_SECRET,
    algorithm: str = "HS256",
) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.mark.parametrize(
    ("role", "user_id"),
    [
        ("admin", "usr_local_admin"),
        ("issuer", "usr_local_issuer"),
        ("verifier", "usr_local_verifier"),
    ],
)
def test_login_succeeds_for_each_synthetic_role(
    client: TestClient,
    role: str,
    user_id: str,
) -> None:
    token, body = login(client, role)

    assert token.count(".") == 2
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == 900
    assert body["user"]["id"] == user_id
    assert body["user"]["roles"] == [role]
    assert body["user"]["username"] == f"{role}@example.test"
    assert "password" not in body["user"]
    assert "authenticationSource" not in body["user"]


def test_login_response_is_non_cacheable_and_secret_free(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": "issuer@example.test",
            "password": PASSWORDS["issuer"],
        },
        headers={"x-request-id": "login-request-1"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-request-id"] == "login-request-1"
    assert PASSWORDS["issuer"] not in response.text
    assert TEST_SECRET not in response.text
    assert "$argon2" not in response.text


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("missing@example.test", "Wrong-Password-2026!"),
        ("issuer@example.test", "Wrong-Password-2026!"),
        ("disabled@example.test", PASSWORDS["disabled"]),
    ],
)
def test_invalid_login_uses_one_public_401_shape(
    client: TestClient,
    username: str,
    password: str,
) -> None:
    response = client.post(
        "/api/v1/auth/token",
        json={"username": username, "password": password},
    )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "INVALID_CREDENTIALS",
        "message": "Invalid username or password.",
        "details": [],
    }
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["cache-control"] == "no-store"
    assert password not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "password"},
        {"username": "issuer@example.test"},
        {"username": "", "password": "password"},
        {"username": "   ", "password": "password"},
        {"username": "issuer@example.test", "password": ""},
        {
            "username": "issuer@example.test",
            "password": "password",
            "unexpected": True,
        },
    ],
)
def test_login_request_envelope_is_strict(
    client: TestClient,
    payload: dict[str, Any],
) -> None:
    response = client.post("/api/v1/auth/token", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_login_rejects_duplicate_json_and_oversized_body(
    client: TestClient,
) -> None:
    duplicate = client.post(
        "/api/v1/auth/token",
        content=(
            '{"username":"issuer@example.test",'
            '"username":"admin@example.test","password":"x"}'
        ),
        headers={"content-type": "application/json"},
    )
    oversized = client.post(
        "/api/v1/auth/token",
        content=b"x" * 4_097,
        headers={"content-type": "application/json"},
    )

    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_JSON_PROPERTY"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_disabled_auth_configuration_fails_closed(
    client: TestClient,
    auth_context: AuthContext,
) -> None:
    disabled_service = AuthenticationService(
        user_provider=auth_context.provider,
        password_hasher=Argon2PasswordHasher(),
        access_token_service=auth_context.token_service,
        clock=lambda: FIXED_TIME,
        jti_generator=lambda: "unused",
        enabled=False,
    )
    app.dependency_overrides[get_authentication_service] = (
        lambda: disabled_service
    )

    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": "issuer@example.test",
            "password": PASSWORDS["issuer"],
        },
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "AUTH_CONFIGURATION_ERROR"
    assert response.json()["error"]["message"] == (
        "Authentication is not safely configured."
    )


def test_login_body_and_password_are_not_logged(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    password = "Log-Probe-Password-2026!"
    response = client.post(
        "/api/v1/auth/token",
        json={
            "username": "unknown@example.test",
            "password": password,
        },
    )

    assert response.status_code == 401
    assert password not in caplog.text
    assert "unknown@example.test" not in caplog.text
    assert response.request.content.decode("utf-8") not in caplog.text


@pytest.mark.parametrize("role", ["admin", "issuer", "verifier"])
def test_auth_me_returns_current_public_user(
    client: TestClient,
    role: str,
) -> None:
    token, login_body = login(client, role)

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["id"] == login_body["user"]["id"]
    assert response.json()["roles"] == [role]
    assert (
        response.json()["authenticationSource"]
        == "local-synthetic-fixture"
    )
    assert "password" not in response.json()
    assert "$argon2" not in response.text
    assert token not in response.text


def test_auth_me_without_or_with_malformed_token_returns_401(
    client: TestClient,
) -> None:
    missing = client.get("/api/v1/auth/me")
    malformed = client.get(
        "/api/v1/auth/me",
        headers=bearer("malformed.token.value"),
    )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert malformed.status_code == 401
    assert malformed.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"
    assert missing.headers["www-authenticate"] == "Bearer"
    assert malformed.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda value: value.update(
                {"exp": int((FIXED_TIME - timedelta(minutes=1)).timestamp())}
            ),
            "ACCESS_TOKEN_EXPIRED",
        ),
        (
            lambda value: value.update({"iss": "wrong-issuer"}),
            "ACCESS_TOKEN_INVALID_ISSUER",
        ),
        (
            lambda value: value.update({"aud": "wrong-audience"}),
            "ACCESS_TOKEN_INVALID_AUDIENCE",
        ),
        (
            lambda value: value.update({"token_use": "refresh"}),
            "ACCESS_TOKEN_INVALID_USE",
        ),
    ],
)
def test_auth_me_maps_token_failures_to_specific_safe_codes(
    client: TestClient,
    auth_context: AuthContext,
    mutation: Any,
    expected_code: str,
) -> None:
    token = issue_for(
        auth_context,
        principal_for(auth_context.provider, "issuer@example.test"),
    )
    payload = raw_payload(token)
    mutation(payload)

    response = client.get(
        "/api/v1/auth/me",
        headers=bearer(encode_payload(payload)),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == expected_code
    assert "jwt." not in response.text.lower()


def test_auth_me_rejects_disabled_and_unknown_current_users(
    client: TestClient,
    auth_context: AuthContext,
) -> None:
    disabled = issue_for(
        auth_context,
        principal_for(auth_context.provider, "disabled@example.test"),
    )
    missing = issue_for(
        auth_context,
        AuthenticatedPrincipal.from_user(
            User(
                id="usr_missing",
                username="missing@example.test",
                display_name="Missing User",
                roles=(Role.ISSUER,),
            ),
            authentication_source="local-synthetic-fixture",
        ),
    )

    disabled_response = client.get(
        "/api/v1/auth/me",
        headers=bearer(disabled),
    )
    missing_response = client.get(
        "/api/v1/auth/me",
        headers=bearer(missing),
    )

    assert disabled_response.status_code == 401
    assert disabled_response.json()["error"]["code"] == "USER_DISABLED"
    assert missing_response.status_code == 401
    assert missing_response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_stale_role_claims_are_not_trusted(
    client: TestClient,
    auth_context: AuthContext,
) -> None:
    old_principal = principal_for(
        auth_context.provider,
        "issuer@example.test",
    )
    token = issue_for(auth_context, old_principal)
    original = auth_context.provider.find_by_username("issuer@example.test")
    assert original is not None
    changed_provider = LocalSyntheticUserProvider(
        (
            LocalAuthenticationRecord(
                user=User(
                    id=original.user.id,
                    username=original.user.username,
                    display_name=original.user.display_name,
                    roles=(Role.VERIFIER,),
                ),
                password_hash=original.password_hash,
            ),
        )
    )
    changed_service = AuthenticationService(
        user_provider=changed_provider,
        password_hasher=Argon2PasswordHasher(),
        access_token_service=auth_context.token_service,
        clock=lambda: FIXED_TIME,
        jti_generator=lambda: "unused",
    )
    app.dependency_overrides[get_authentication_service] = (
        lambda: changed_service
    )

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"


def test_sign_requires_authentication_before_service_execution(
    client: TestClient,
) -> None:
    class SignSpy:
        calls = 0

        def sign_credential(self, credential: Any) -> None:
            self.calls += 1
            raise AssertionError("Signing must not run.")

    spy = SignSpy()
    app.dependency_overrides[get_credential_api_service] = lambda: spy

    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(UNSIGNED_PATH)},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert spy.calls == 0
    assert "proof" not in response.text


def test_verifier_is_forbidden_before_service_execution(
    client: TestClient,
) -> None:
    class SignSpy:
        calls = 0

        def sign_credential(self, credential: Any) -> None:
            self.calls += 1
            raise AssertionError("Signing must not run.")

    token, body = login(client, "verifier")
    spy = SignSpy()
    app.dependency_overrides[get_credential_api_service] = lambda: spy

    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(UNSIGNED_PATH)},
        headers=bearer(token),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert spy.calls == 0
    assert "credentials:sign" not in body["user"]["permissions"]
    assert "proof" not in response.text


@pytest.mark.parametrize("role", ["issuer", "admin"])
def test_issuer_and_admin_can_use_existing_signing_flow(
    client: TestClient,
    role: str,
) -> None:
    token, _ = login(client, role)

    response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(UNSIGNED_PATH)},
        headers=bearer(token),
    )

    assert response.status_code == 201
    proof = response.json()["credential"]["proof"]
    assert proof["type"] == "DataIntegrityProof"
    assert proof["cryptosuite"] == "eddsa-jcs-2022"
    assert TEST_SECRET not in response.text
    assert "$argon2" not in response.text


def test_expired_and_malformed_tokens_cannot_sign(
    client: TestClient,
    auth_context: AuthContext,
) -> None:
    principal = principal_for(
        auth_context.provider,
        "issuer@example.test",
    )
    expired = issue_for(
        auth_context,
        principal,
        issued_at=FIXED_TIME - timedelta(hours=1),
    )

    malformed_response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(UNSIGNED_PATH)},
        headers=bearer("bad.token.value"),
    )
    expired_response = client.post(
        "/api/v1/credentials/sign",
        json={"credential": load_json(UNSIGNED_PATH)},
        headers=bearer(expired),
    )

    assert malformed_response.status_code == 401
    assert expired_response.status_code == 401
    assert (
        expired_response.json()["error"]["code"]
        == "ACCESS_TOKEN_EXPIRED"
    )


def test_validate_verify_capabilities_and_health_remain_public(
    client: TestClient,
) -> None:
    validate = client.post(
        "/api/v1/credentials/validate",
        json={"credential": load_json(UNSIGNED_PATH)},
    )
    verify = client.post(
        "/api/v1/credentials/verify",
        json={"credential": load_json(SIGNED_PATH)},
    )
    capabilities = client.get("/api/v1/credentials/capabilities")
    health = client.get("/health")

    assert validate.status_code == 200
    assert verify.status_code == 200
    assert capabilities.status_code == 200
    assert health.status_code == 200


def test_openapi_declares_only_me_and_sign_as_bearer_protected() -> None:
    schema = app.openapi()
    schemes = schema["components"]["securitySchemes"]

    assert schemes["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "Short-lived local prototype JWT. Synthetic accounts only; no "
            "refresh token or production identity provider."
        ),
    }
    protected = {
        ("get", "/api/v1/auth/me"),
        ("post", "/api/v1/credentials/sign"),
    }
    public = {
        ("post", "/api/v1/auth/token"),
        ("post", "/api/v1/credentials/validate"),
        ("post", "/api/v1/credentials/verify"),
        ("get", "/api/v1/credentials/capabilities"),
    }
    for method, path in protected:
        assert schema["paths"][path][method]["security"] == [
            {"BearerAuth": []}
        ]
    for method, path in public:
        assert "security" not in schema["paths"][path][method]


def test_openapi_response_schemas_exclude_authentication_secrets() -> None:
    schemas = app.openapi()["components"]["schemas"]
    forbidden = {
        "passwordhash",
        "jwtsecret",
        "seed",
        "privatekey",
        "signingcapability",
    }

    for schema_name, schema in schemas.items():
        properties = schema.get("properties", {})
        normalized = {
            name.replace("_", "").lower() for name in properties
        }
        assert not normalized.intersection(forbidden)
        if "password" in properties:
            assert schema_name == "TokenRequest"
    assert "AuthenticationRecord" not in schemas
    assert "password" not in schemas["PublicUserResponse"]["properties"]
    assert "password" not in schemas["CurrentUserResponse"]["properties"]


def test_safe_500_never_logs_or_returns_bearer_token(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = "sensitive.header.payload"

    class FailingAuthenticationService:
        def authenticate_access_token(self, value: str) -> None:
            raise RuntimeError("SensitiveAuthFailureClass internal")

    app.dependency_overrides[get_authentication_service] = (
        lambda: FailingAuthenticationService()
    )

    response = client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert token not in response.text
    assert token not in caplog.text
    assert f"Bearer {token}" not in caplog.text
    assert "RuntimeError" not in response.text
    assert "SensitiveAuthFailureClass" not in response.text
    assert "Traceback" not in response.text
