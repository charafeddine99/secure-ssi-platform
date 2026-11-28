from datetime import UTC, datetime
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from app.application.ports.repositories import RecoveryRepository
from app.core.config import RecoverySettings
from app.domain.auth import RecoveryPrincipal
from app.domain.recovery import RecoveryAuthorizationError


STEP_UP_AUDIENCE = "secure-ssi-step-up"
_REQUIRED = ["iss", "sub", "aud", "iat", "exp", "jti", "sid", "act", "res"]


class StepUpRequiredError(RecoveryAuthorizationError):
    """A fresh second factor is missing, stale, replayed or for something else."""


class StepUpGuard:
    """Accepts a token only for this session, action and resource, and once."""

    def __init__(
        self,
        settings: RecoverySettings,
        repository: RecoveryRepository,
    ) -> None:
        self._settings = settings
        self._repository = repository

    def require(
        self,
        principal: RecoveryPrincipal,
        token: str | None,
        *,
        action: str,
        resource: str,
    ) -> None:
        if not self._settings.step_up_required:
            return
        if not token or len(token) > 4096:
            raise StepUpRequiredError("Fresh authentication is required.")
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._settings.step_up_secret,
                algorithms=["HS256"],
                audience=STEP_UP_AUDIENCE,
                issuer=self._settings.jwt_issuer,
                options={"require": _REQUIRED, "strict_aud": True},
            )
        except (InvalidTokenError, ValueError) as error:
            raise StepUpRequiredError(
                "Fresh authentication is required."
            ) from error
        if (
            claims["sub"] != principal.user_id
            or claims["sid"] != principal.session_id
            or claims["act"] != action
            or claims["res"] != resource
        ):
            raise StepUpRequiredError("Fresh authentication is required.")
        expires_at = datetime.fromtimestamp(int(claims["exp"]), UTC)
        if not self._repository.consume_step_up(
            str(claims["jti"]),
            expires_at=expires_at,
        ):
            raise StepUpRequiredError("Fresh authentication is required.")
