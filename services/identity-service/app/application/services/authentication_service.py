from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from app.application.ports.access_token_service import AccessTokenService
from app.application.ports.auth_runtime import JtiGenerator
from app.application.ports.password_hasher import PasswordHasherPort
from app.application.ports.user_provider import UserProvider
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import (
    AccessTokenRevokedError,
    AuthConfigurationError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    UserDisabledError,
    UserNotFoundError,
)
from app.infrastructure.auth.token_revocation import (
    TokenRevocationStore,
    get_token_revocation_store,
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
        revocation_store: TokenRevocationStore | None = None,
        enabled: bool = True,
    ) -> None:
        self.user_provider = user_provider
        self.password_hasher = password_hasher
        self.access_token_service = access_token_service
        self.clock = clock
        self.jti_generator = jti_generator
        self.revocation_store = (
            revocation_store
            if revocation_store is not None
            else get_token_revocation_store()
        )
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
        if self.revocation_store is not None and self.revocation_store.is_revoked(
            claims.jwt_id, claims.subject, claims.issued_at
        ):
            raise AccessTokenRevokedError("Access token has been revoked.")

        record = self.user_provider.find_by_id(claims.subject)
        if record is None:
            raise UserNotFoundError("Token subject is not registered.")
        if not record.user.enabled:
            raise UserDisabledError("Token subject is disabled.")
        if claims.roles != record.user.roles:
            raise InvalidAccessTokenError(
                "Token roles do not match the current local user."
            )
        return replace(
            AuthenticatedPrincipal.from_user(
                record.user,
                authentication_source=self.user_provider.authentication_source,
            ),
            session_id=claims.jwt_id,
        )

    def is_session_active(
        self,
        *,
        user_id: str,
        session_id: str,
        issued_at: datetime,
    ) -> bool:
        return self.revocation_store is None or not (
            self.revocation_store.is_revoked(session_id, user_id, issued_at)
        )

    def revoke_token(self, token: str, reason: str = "logout") -> None:
        """Revokes a specific token by decoding its JTI and blacklisting it."""
        if self.revocation_store is None:
            return
        claims = self.access_token_service.decode_access_token(
            token,
            checked_at=self.clock(),
        )
        self.revocation_store.revoke_token(
            jti=claims.jwt_id,
            expires_at=claims.expires_at,
            reason=reason,
        )

    def revoke_subject(self, subject: str, reason: str = "security_quarantine") -> None:
        """Revokes all active sessions for a given subject (user/DID)."""
        if self.revocation_store is not None:
            self.revocation_store.revoke_subject(subject, reason=reason)

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise AuthConfigurationError(
                "Local authentication is disabled by configuration."
            )
