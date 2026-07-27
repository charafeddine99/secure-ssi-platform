from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.ports.access_token_service import AccessTokenService
from app.application.ports.auth_runtime import JtiGenerator
from app.application.ports.password_hasher import PasswordHasherPort
from app.application.ports.user_provider import UserProvider
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import (
    AuthConfigurationError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    UserDisabledError,
    UserNotFoundError,
)


@dataclass(frozen=True)
class AuthenticationSession:
    access_token: str
    expires_in: int
    principal: AuthenticatedPrincipal


class AuthenticationService:
    def __init__(
        self,
        *,
        user_provider: UserProvider,
        password_hasher: PasswordHasherPort,
        access_token_service: AccessTokenService,
        clock: Callable[[], datetime],
        jti_generator: JtiGenerator,
        enabled: bool = True,
    ) -> None:
        self.user_provider = user_provider
        self.password_hasher = password_hasher
        self.access_token_service = access_token_service
        self.clock = clock
        self.jti_generator = jti_generator
        self.enabled = enabled

    def authenticate(
        self,
        *,
        username: str,
        password: str,
    ) -> AuthenticationSession:
        self._ensure_enabled()
        record = self.user_provider.find_by_username(username)
        password_hash = (
            record.password_hash
            if record is not None
            else self.user_provider.fallback_password_hash()
        )
        password_valid = self.password_hasher.verify_password(
            password,
            password_hash,
        )
        if record is None or not password_valid or not record.user.enabled:
            raise InvalidCredentialsError("Local credentials are invalid.")

        principal = AuthenticatedPrincipal.from_user(
            record.user,
            authentication_source=self.user_provider.authentication_source,
        )
        issued_at = self.clock()
        token = self.access_token_service.issue_access_token(
            principal,
            issued_at=issued_at,
            jwt_id=self.jti_generator(),
        )
        return AuthenticationSession(
            access_token=token,
            expires_in=self.access_token_service.lifetime_seconds,
            principal=principal,
        )

    def authenticate_access_token(
        self,
        token: str,
    ) -> AuthenticatedPrincipal:
        self._ensure_enabled()
        claims = self.access_token_service.decode_access_token(
            token,
            checked_at=self.clock(),
        )
        record = self.user_provider.find_by_id(claims.subject)
        if record is None:
            raise UserNotFoundError("Token subject is not registered.")
        if not record.user.enabled:
            raise UserDisabledError("Token subject is disabled.")
        if claims.roles != record.user.roles:
            raise InvalidAccessTokenError(
                "Token roles do not match the current local user."
            )
        return AuthenticatedPrincipal.from_user(
            record.user,
            authentication_source=self.user_provider.authentication_source,
        )

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise AuthConfigurationError(
                "Local authentication is disabled by configuration."
            )
