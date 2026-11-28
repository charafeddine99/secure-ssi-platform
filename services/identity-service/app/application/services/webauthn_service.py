"""WebAuthn registration and step-up. All ceremony checks (challenge, origin,
RP ID, user verification, signature, counter) are done by py_webauthn."""

import base64
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

from app.application.services.step_up_service import (
    StepUpRequiredError,
    StepUpService,
)
from app.config.environment_policy import is_production_like
from app.domain.auth import AuthenticatedPrincipal
from app.domain.persistence import (
    PersistenceConfigurationError,
    PersistenceUnavailableError,
)


WEBAUTHN_CREDENTIALS_COLLECTION = "webauthn_credentials"
WEBAUTHN_CHALLENGES_COLLECTION = "webauthn_challenges"
_CHALLENGE_LIFETIME = timedelta(minutes=5)


@dataclass(frozen=True)
class WebAuthnSettings:
    rp_id: str | None = None
    origin: str | None = None
    rp_name: str = "Secure SSI"

    @property
    def configured(self) -> bool:
        return self.rp_id is not None and self.origin is not None


def load_webauthn_settings(
    environ: Mapping[str, str] | None = None,
) -> WebAuthnSettings:
    values = os.environ if environ is None else environ
    rp_id = values.get("IDENTITY_WEBAUTHN_RP_ID", "").strip() or None
    origin = values.get("IDENTITY_WEBAUTHN_ORIGIN", "").strip() or None
    if bool(rp_id) != bool(origin):
        raise PersistenceConfigurationError(
            "WebAuthn needs both an RP ID and an origin."
        )
    production = is_production_like(
        values.get("IDENTITY_ENVIRONMENT", "development")
    )
    if production and origin is not None and not origin.startswith("https://"):
        raise PersistenceConfigurationError(
            "A production-like WebAuthn origin must use HTTPS."
        )
    return WebAuthnSettings(rp_id=rp_id, origin=origin)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class WebAuthnService:
    def __init__(
        self,
        *,
        credentials: Collection[dict[str, Any]],
        challenges: Collection[dict[str, Any]],
        settings: WebAuthnSettings,
        step_up: StepUpService,
        clock: Callable[[], datetime],
    ) -> None:
        self._credentials = credentials
        self._challenges = challenges
        self._settings = settings
        self._step_up = step_up
        self._clock = clock

    @property
    def configured(self) -> bool:
        return self._settings.configured

    def enrolled(self, user_id: str) -> bool:
        try:
            return self._credentials.find_one({"userId": user_id}) is not None
        except PyMongoError as error:
            raise _unavailable() from error

    def registration_options(
        self,
        principal: AuthenticatedPrincipal,
    ) -> dict[str, Any]:
        self._require_configured()
        options = generate_registration_options(
            rp_id=self._settings.rp_id,
            rp_name=self._settings.rp_name,
            user_id=principal.id.encode(),
            user_name=principal.username,
            user_display_name=principal.display_name,
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=_unb64(item["_id"]))
                for item in self._owned(principal.id)
            ],
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        self._store_challenge(
            principal,
            options.challenge,
            purpose="register",
        )
        return json.loads(options_to_json(options))

    def verify_registration(
        self,
        principal: AuthenticatedPrincipal,
        credential: Mapping[str, Any],
    ) -> None:
        self._require_configured()
        challenge = self._take_challenge(principal, purpose="register")
        try:
            verified = verify_registration_response(
                credential=dict(credential),
                expected_challenge=challenge,
                expected_rp_id=self._settings.rp_id,
                expected_origin=self._settings.origin,
                require_user_verification=True,
            )
        except (WebAuthnException, ValueError, KeyError, TypeError) as error:
            raise StepUpRequiredError(
                "The authenticator response was not accepted."
            ) from error
        try:
            self._credentials.insert_one(
                {
                    "_id": _b64(verified.credential_id),
                    "userId": principal.id,
                    "publicKey": _b64(verified.credential_public_key),
                    "signCount": verified.sign_count,
                    "createdAt": self._now(),
                }
            )
        except DuplicateKeyError as error:
            raise StepUpRequiredError(
                "This authenticator is already registered."
            ) from error
        except PyMongoError as error:
            raise _unavailable() from error

    def authentication_options(
        self,
        principal: AuthenticatedPrincipal,
        *,
        action: str,
        resource: str,
    ) -> dict[str, Any]:
        self._require_configured()
        owned = self._owned(principal.id)
        if not owned:
            raise StepUpRequiredError("No authenticator is registered.")
        options = generate_authentication_options(
            rp_id=self._settings.rp_id,
            allow_credentials=[
                PublicKeyCredentialDescriptor(id=_unb64(item["_id"]))
                for item in owned
            ],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        self._store_challenge(
            principal,
            options.challenge,
            purpose="step-up",
            action=action,
            resource=resource,
        )
        return json.loads(options_to_json(options))

    def verify_step_up(
        self,
        principal: AuthenticatedPrincipal,
        credential: Mapping[str, Any],
        *,
        action: str,
        resource: str,
    ) -> tuple[str, int]:
        """The challenge names one action and resource, and is used once."""
        self._require_configured()
        challenge = self._take_challenge(
            principal,
            purpose="step-up",
            action=action,
            resource=resource,
        )
        try:
            stored = self._credentials.find_one(
                {"_id": str(credential.get("id")), "userId": principal.id}
            )
        except PyMongoError as error:
            raise _unavailable() from error
        if stored is None:
            raise StepUpRequiredError("This authenticator is not registered.")
        try:
            verified = verify_authentication_response(
                credential=dict(credential),
                expected_challenge=challenge,
                expected_rp_id=self._settings.rp_id,
                expected_origin=self._settings.origin,
                credential_public_key=_unb64(stored["publicKey"]),
                credential_current_sign_count=int(stored["signCount"]),
                require_user_verification=True,
            )
        except (WebAuthnException, ValueError, KeyError, TypeError) as error:
            raise StepUpRequiredError(
                "The authenticator response was not accepted."
            ) from error
        self._credentials.update_one(
            {"_id": stored["_id"]},
            {"$set": {"signCount": verified.new_sign_count}},
        )
        return self._step_up.mint_token(
            principal,
            action=action,
            resource=resource,
            method="webauthn",
        )

    def _owned(self, user_id: str) -> list[dict[str, Any]]:
        try:
            return list(self._credentials.find({"userId": user_id}))
        except PyMongoError as error:
            raise _unavailable() from error

    def _store_challenge(
        self,
        principal: AuthenticatedPrincipal,
        challenge: bytes,
        *,
        purpose: str,
        action: str = "",
        resource: str = "",
    ) -> None:
        key = f"{principal.id}:{principal.session_id}:{purpose}"
        try:
            self._challenges.update_one(
                {"_id": key},
                {
                    "$set": {
                        "challenge": _b64(challenge),
                        "action": action,
                        "resource": resource,
                        "expiresAt": self._now() + _CHALLENGE_LIFETIME,
                        "used": False,
                    }
                },
                upsert=True,
            )
        except PyMongoError as error:
            raise _unavailable() from error

    def _take_challenge(
        self,
        principal: AuthenticatedPrincipal,
        *,
        purpose: str,
        action: str = "",
        resource: str = "",
    ) -> bytes:
        key = f"{principal.id}:{principal.session_id}:{purpose}"
        try:
            document = self._challenges.find_one({"_id": key})
            if document is None or document.get("used") is not False:
                raise StepUpRequiredError("Start the authenticator check again.")
            expires_at = document["expiresAt"]
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if (
                expires_at <= self._now()
                or document["action"] != action
                or document["resource"] != resource
            ):
                raise StepUpRequiredError("Start the authenticator check again.")
            result = self._challenges.update_one(
                {"_id": key, "used": False},
                {"$set": {"used": True}},
            )
        except PyMongoError as error:
            raise _unavailable() from error
        if result.matched_count != 1:
            raise StepUpRequiredError("Start the authenticator check again.")
        return _unb64(document["challenge"])

    def _require_configured(self) -> None:
        if not self._settings.configured:
            raise StepUpRequiredError(
                "Security keys are not configured on this deployment."
            )

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)


def _unavailable() -> PersistenceUnavailableError:
    return PersistenceUnavailableError("Authenticator data is unavailable.")
