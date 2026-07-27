from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from app.config.auth_settings import AuthSettings
from app.domain.auth import AuthenticatedPrincipal, User
from app.domain.exceptions import (
    AccessTokenExpiredError,
    AccessTokenInvalidAudienceError,
    AccessTokenInvalidIssuerError,
    AccessTokenInvalidUseError,
    AccessTokenNotActiveError,
    InvalidAccessTokenError,
)
from app.domain.permissions import Role
from app.infrastructure.auth.jwt_access_token_service import (
    JwtAccessTokenService,
)


TEST_SECRET = "test-only-jwt-secret-with-at-least-thirty-two-bytes"
OTHER_SECRET = "different-test-secret-with-at-least-thirty-two-bytes"
FIXED_TIME = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> AuthSettings:
    return AuthSettings(
        enabled=True,
        jwt_issuer="test-secure-ssi",
        jwt_audience="identity-service",
        access_token_lifetime_seconds=900,
        jwt_algorithm="HS256",
        jwt_secret=TEST_SECRET,
        local_fixture_users_enabled=True,
        clock_skew_seconds=10,
        environment="test",
    )


@pytest.fixture
def principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal.from_user(
        User(
            id="usr_test_issuer",
            username="issuer@example.test",
            display_name="Test Issuer",
            roles=(Role.ISSUER,),
        ),
        authentication_source="local-synthetic-fixture",
    )


def issue(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> tuple[JwtAccessTokenService, str]:
    service = JwtAccessTokenService(settings)
    token = service.issue_access_token(
        principal,
        issued_at=FIXED_TIME,
        jwt_id="fixed-test-jti",
    )
    return service, token


def payload(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        options={"verify_signature": False},
        algorithms=["HS256"],
    )


def encode(
    value: dict[str, Any],
    *,
    secret: str = TEST_SECRET,
    algorithm: str = "HS256",
) -> str:
    return jwt.encode(value, secret, algorithm=algorithm)


def test_access_token_contains_all_required_claims_and_is_short_lived(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)

    assert claims == {
        "iss": "test-secure-ssi",
        "sub": "usr_test_issuer",
        "aud": "identity-service",
        "iat": int(FIXED_TIME.timestamp()),
        "nbf": int(FIXED_TIME.timestamp()),
        "exp": int((FIXED_TIME + timedelta(seconds=900)).timestamp()),
        "jti": "fixed-test-jti",
        "roles": ["issuer"],
        "token_use": "access",
    }
    assert service.lifetime_seconds == 900


def test_valid_token_is_verified_deterministically(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, first = issue(settings, principal)
    _, second = issue(settings, principal)

    assert first == second
    decoded = service.decode_access_token(
        first,
        checked_at=FIXED_TIME,
    )
    assert decoded.subject == principal.id
    assert decoded.roles == (Role.ISSUER,)


def test_expired_token_is_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)

    with pytest.raises(AccessTokenExpiredError):
        service.decode_access_token(
            token,
            checked_at=FIXED_TIME + timedelta(seconds=911),
        )


@pytest.mark.parametrize("claim", ["nbf", "iat"])
def test_future_time_claim_is_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
    claim: str,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims[claim] = int((FIXED_TIME + timedelta(minutes=2)).timestamp())

    with pytest.raises(AccessTokenNotActiveError):
        service.decode_access_token(
            encode(claims),
            checked_at=FIXED_TIME,
        )


def test_wrong_issuer_is_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims["iss"] = "wrong-issuer"

    with pytest.raises(AccessTokenInvalidIssuerError):
        service.decode_access_token(
            encode(claims),
            checked_at=FIXED_TIME,
        )


def test_wrong_audience_is_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims["aud"] = "wrong-service"

    with pytest.raises(AccessTokenInvalidAudienceError):
        service.decode_access_token(
            encode(claims),
            checked_at=FIXED_TIME,
        )


def test_wrong_signature_is_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)

    with pytest.raises(InvalidAccessTokenError):
        service.decode_access_token(
            encode(payload(token), secret=OTHER_SECRET),
            checked_at=FIXED_TIME,
        )


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda claims: jwt.encode(claims, key="", algorithm="none"),
        lambda claims: encode(claims, algorithm="HS384"),
    ],
)
def test_none_and_non_allowlisted_algorithms_are_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
    token_factory: Any,
) -> None:
    service, token = issue(settings, principal)

    with pytest.raises(InvalidAccessTokenError):
        service.decode_access_token(
            token_factory(payload(token)),
            checked_at=FIXED_TIME,
        )


@pytest.mark.parametrize("missing_claim", ["exp", "sub"])
def test_required_claims_are_enforced(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
    missing_claim: str,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims.pop(missing_claim)

    with pytest.raises(InvalidAccessTokenError):
        service.decode_access_token(
            encode(claims),
            checked_at=FIXED_TIME,
        )


def test_wrong_token_use_is_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims["token_use"] = "refresh"

    with pytest.raises(AccessTokenInvalidUseError):
        service.decode_access_token(
            encode(claims),
            checked_at=FIXED_TIME,
        )


def test_unknown_role_is_never_trusted(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims["roles"] = ["issuer", "owner"]

    with pytest.raises(InvalidAccessTokenError):
        service.decode_access_token(
            encode(claims),
            checked_at=FIXED_TIME,
        )


def test_duplicate_roles_are_normalized(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims["roles"] = ["issuer", "issuer"]

    decoded = service.decode_access_token(
        encode(claims),
        checked_at=FIXED_TIME,
    )

    assert decoded.roles == (Role.ISSUER,)


def test_excessive_signed_lifetime_is_rejected(
    settings: AuthSettings,
    principal: AuthenticatedPrincipal,
) -> None:
    service, token = issue(settings, principal)
    claims = payload(token)
    claims["exp"] = int((FIXED_TIME + timedelta(hours=2)).timestamp())

    with pytest.raises(InvalidAccessTokenError):
        service.decode_access_token(
            encode(claims),
            checked_at=FIXED_TIME,
        )


def test_malformed_token_error_does_not_echo_token_or_secret(
    settings: AuthSettings,
) -> None:
    service = JwtAccessTokenService(settings)
    malformed = "malformed.sensitive.token"

    with pytest.raises(InvalidAccessTokenError) as captured:
        service.decode_access_token(malformed, checked_at=FIXED_TIME)

    assert malformed not in str(captured.value)
    assert TEST_SECRET not in str(captured.value)
    assert TEST_SECRET not in repr(service)
