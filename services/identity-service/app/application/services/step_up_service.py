"""TOTP step-up. RFC 6238 maths comes from pyotp; this module only stores the
factor, applies replay and lockout rules, and issues narrowly scoped tokens."""

import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jwt.exceptions import InvalidTokenError
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.config.step_up_settings import StepUpSettings
from app.domain.auth import AuthenticatedPrincipal
from app.domain.exceptions import PermissionDeniedError
from app.domain.persistence import PersistenceUnavailableError


STEP_UP_AUDIENCE = "secure-ssi-step-up"
MFA_FACTORS_COLLECTION = "mfa_factors"
STEP_UP_TOKENS_COLLECTION = "step_up_tokens"
_TOTP_PERIOD = 30
_REQUIRED_CLAIMS = ["iss", "sub", "aud", "iat", "exp", "jti", "sid", "act", "res"]


class StepUpRequiredError(PermissionDeniedError):
    """A fresh second factor is missing, stale, replayed or for something else."""


class StepUpLockedError(StepUpRequiredError):
    """Too many wrong codes; the factor is locked for a while."""


@dataclass(frozen=True)
class TotpEnrollment:
    secret: str
    otpauth_uri: str


class StepUpService:
    def __init__(
        self,
        *,
        factors: Collection[dict[str, Any]],
        tokens: Collection[dict[str, Any]],
        settings: StepUpSettings,
        issuer: str,
        clock: Callable[[], datetime],
    ) -> None:
        self._factors = factors
        self._tokens = tokens
        self._settings = settings
        self._issuer = issuer
        self._clock = clock

    @property
    def required(self) -> bool:
        return self._settings.required

    def status(self, user_id: str) -> dict[str, Any]:
        factor = self._factor(user_id)
        return {
            "required": self._settings.required,
            "enrolled": bool(factor and factor.get("confirmed")),
            "method": "TOTP" if factor and factor.get("confirmed") else None,
        }

    def begin_enrollment(
        self,
        principal: AuthenticatedPrincipal,
        *,
        current_code: str | None,
    ) -> TotpEnrollment:
        """A confirmed factor can only be replaced by proving that factor."""
        existing = self._factor(principal.id)
        if existing is not None and existing.get("confirmed"):
            if not current_code:
                raise StepUpRequiredError(
                    "The current authenticator code is required."
                )
            self._check_code(existing, current_code)
            existing = self._factor(principal.id)
        secret = pyotp.random_base32()
        now = self._now()
        document = {
            "userId": principal.id,
            "confirmed": False,
            "pendingSecret": self._seal(principal.id, secret),
            "secret": existing.get("secret") if existing else None,
            "lastCounter": existing.get("lastCounter", 0) if existing else 0,
            "failedAttempts": 0,
            "lockedUntil": None,
            "version": (existing.get("version", 0) if existing else 0) + 1,
            "updatedAt": now,
        }
        if existing is not None and existing.get("confirmed"):
            document["confirmed"] = True
        self._write(principal.id, document, existing)
        return TotpEnrollment(
            secret=secret,
            otpauth_uri=pyotp.TOTP(secret).provisioning_uri(
                name=principal.username,
                issuer_name=self._settings.totp_issuer,
            ),
        )

    def confirm_enrollment(
        self,
        principal: AuthenticatedPrincipal,
        *,
        code: str,
    ) -> None:
        factor = self._factor(principal.id)
        if factor is None or not factor.get("pendingSecret"):
            raise StepUpRequiredError("No authenticator enrollment is open.")
        secret = self._open(principal.id, factor["pendingSecret"])
        counter = self._matching_counter(secret, code)
        if counter is None:
            self._record_failure(factor)
            raise StepUpRequiredError("The authenticator code is invalid.")
        self._write(
            principal.id,
            {
                **factor,
                "confirmed": True,
                "secret": factor["pendingSecret"],
                "pendingSecret": None,
                "lastCounter": counter,
                "failedAttempts": 0,
                "lockedUntil": None,
                "version": factor.get("version", 0) + 1,
                "updatedAt": self._now(),
            },
            factor,
        )

    def issue_token(
        self,
        principal: AuthenticatedPrincipal,
        *,
        action: str,
        resource: str,
        code: str,
    ) -> tuple[str, int]:
        factor = self._factor(principal.id)
        if factor is None or not factor.get("confirmed"):
            raise StepUpRequiredError("No authenticator is enrolled.")
        self._check_code(factor, code)
        return self.mint_token(
            principal,
            action=action,
            resource=resource,
            method="otp",
        )

    def mint_token(
        self,
        principal: AuthenticatedPrincipal,
        *,
        action: str,
        resource: str,
        method: str,
    ) -> tuple[str, int]:
        """Only for callers that have just verified a factor themselves."""
        now = self._now()
        lifetime = self._settings.token_lifetime_seconds
        token = jwt.encode(
            {
                "iss": self._issuer,
                "sub": principal.id,
                "aud": STEP_UP_AUDIENCE,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(seconds=lifetime)).timestamp()),
                "jti": secrets.token_urlsafe(24),
                "sid": principal.session_id,
                "act": action,
                "res": resource,
                "amr": [method],
            },
            self._settings.token_secret,
            algorithm="HS256",
        )
        return token, lifetime

    def require(
        self,
        principal: AuthenticatedPrincipal,
        token: str | None,
        *,
        action: str,
        resource: str,
    ) -> None:
        """No-op only when the setting allows it, which production never does."""
        if not self._settings.required:
            return
        if not token or len(token) > 4096:
            raise StepUpRequiredError("Fresh authentication is required.")
        try:
            claims = jwt.decode(
                token,
                self._settings.token_secret,
                algorithms=["HS256"],
                audience=STEP_UP_AUDIENCE,
                issuer=self._issuer,
                options={"require": _REQUIRED_CLAIMS, "strict_aud": True},
            )
        except (InvalidTokenError, ValueError) as error:
            raise StepUpRequiredError(
                "Fresh authentication is required."
            ) from error
        if (
            claims["sub"] != principal.id
            or claims["sid"] != principal.session_id
            or claims["act"] != action
            or claims["res"] != resource
        ):
            raise StepUpRequiredError("Fresh authentication is required.")
        try:
            self._tokens.insert_one(
                {
                    "_id": str(claims["jti"]),
                    "expiresAt": datetime.fromtimestamp(
                        int(claims["exp"]), UTC
                    ),
                }
            )
        except DuplicateKeyError as error:
            raise StepUpRequiredError(
                "Fresh authentication is required."
            ) from error
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                "Step-up replay protection is unavailable."
            ) from error

    def _check_code(self, factor: dict[str, Any], code: str) -> None:
        now = self._now()
        locked_until = factor.get("lockedUntil")
        if locked_until is not None and _aware(locked_until) > now:
            raise StepUpLockedError(
                "Too many wrong codes. Wait before trying again."
            )
        secret = self._open(factor["userId"], factor["secret"])
        counter = self._matching_counter(secret, code)
        if counter is None or counter <= int(factor.get("lastCounter", 0)):
            self._record_failure(factor)
            raise StepUpRequiredError("The authenticator code is invalid.")
        updated = {
            **factor,
            "lastCounter": counter,
            "failedAttempts": 0,
            "lockedUntil": None,
            "version": factor.get("version", 0) + 1,
            "updatedAt": now,
        }
        # Compare-and-set: two requests racing with one code cannot both pass.
        self._write(factor["userId"], updated, factor)

    def _matching_counter(self, secret: str, code: str) -> int | None:
        if not isinstance(code, str) or not code.isdigit() or len(code) != 6:
            return None
        totp = pyotp.TOTP(secret)
        now = self._now()
        current = int(now.timestamp()) // _TOTP_PERIOD
        for offset in (-1, 0, 1):
            if hmac.compare_digest(totp.at(now, offset), code):
                return current + offset
        return None

    def _record_failure(self, factor: dict[str, Any]) -> None:
        attempts = int(factor.get("failedAttempts", 0)) + 1
        locked = attempts >= self._settings.max_failed_attempts
        now = self._now()
        self._write(
            factor["userId"],
            {
                **factor,
                "failedAttempts": 0 if locked else attempts,
                "lockedUntil": (
                    now + timedelta(seconds=self._settings.lockout_seconds)
                    if locked
                    else None
                ),
                "version": factor.get("version", 0) + 1,
                "updatedAt": now,
            },
            factor,
            tolerate_conflict=True,
        )

    def _factor(self, user_id: str) -> dict[str, Any] | None:
        try:
            return self._factors.find_one({"userId": user_id})
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                "Authenticator data is unavailable."
            ) from error

    def _write(
        self,
        user_id: str,
        document: dict[str, Any],
        expected: dict[str, Any] | None,
        *,
        tolerate_conflict: bool = False,
    ) -> None:
        fields = {k: v for k, v in document.items() if k != "_id"}
        try:
            if expected is None:
                self._factors.insert_one({"_id": user_id, **fields})
                return
            result = self._factors.update_one(
                {"userId": user_id, "version": expected.get("version", 0)},
                {"$set": fields},
            )
        except DuplicateKeyError as error:
            raise StepUpRequiredError(
                "Authenticator data changed. Try again."
            ) from error
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                "Authenticator data is unavailable."
            ) from error
        if result.matched_count != 1 and not tolerate_conflict:
            raise StepUpRequiredError("Authenticator data changed. Try again.")

    def _seal(self, user_id: str, secret: str) -> str:
        nonce = secrets.token_bytes(12)
        sealed = AESGCM(self._settings.factor_key).encrypt(
            nonce, secret.encode(), user_id.encode()
        )
        return (nonce + sealed).hex()

    def _open(self, user_id: str, value: str) -> str:
        raw = bytes.fromhex(value)
        try:
            return AESGCM(self._settings.factor_key).decrypt(
                raw[:12], raw[12:], user_id.encode()
            ).decode()
        except InvalidTag as error:
            raise PersistenceUnavailableError(
                "Authenticator data cannot be read."
            ) from error

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
