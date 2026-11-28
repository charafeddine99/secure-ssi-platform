import json
import os
from collections.abc import Mapping
from dataclasses import dataclass

from app.config.environment_policy import (
    is_production_like,
    normalize_environment,
)
from app.domain.persistence import PersistenceConfigurationError


LOCAL_DEVELOPMENT_PROVIDER = "local-development"
REMOTE_KMS_PROVIDER = "remote-kms"
_SYNTHETIC_ISSUER_DID = "did:web:issuer.example"


@dataclass(frozen=True)
class HistoricalVerificationKey:
    """Public key of a retired issuer or status key, kept for old proofs."""

    verification_method: str
    public_key_multibase: str


@dataclass(frozen=True)
class SigningTrustSettings:
    environment: str
    provider: str
    issuer_did: str
    issuer_key_reference: str | None = None
    issuer_verification_method: str | None = None
    status_key_reference: str | None = None
    status_verification_method: str | None = None
    issuer_auth_token_env: str | None = None
    status_auth_token_env: str | None = None
    historical_keys: tuple[HistoricalVerificationKey, ...] = ()

    def __post_init__(self) -> None:
        if self.provider not in {
            LOCAL_DEVELOPMENT_PROVIDER,
            REMOTE_KMS_PROVIDER,
        }:
            raise PersistenceConfigurationError(
                "Issuer key provider is not recognised."
            )
        if is_production_like(self.environment):
            self._require_production_shape()
        elif self.provider == REMOTE_KMS_PROVIDER:
            self._require_remote_references()

    def _require_production_shape(self) -> None:
        if self.provider != REMOTE_KMS_PROVIDER:
            raise PersistenceConfigurationError(
                "Production-like environments must sign issuer credentials "
                "and status lists through the remote KMS."
            )
        if self.issuer_did == _SYNTHETIC_ISSUER_DID:
            raise PersistenceConfigurationError(
                "The synthetic issuer identity cannot be used in "
                "production-like environments."
            )
        self._require_remote_references()
        if not self.issuer_auth_token_env or not self.status_auth_token_env:
            raise PersistenceConfigurationError(
                "Issuer and status signing need their own KMS client "
                "credentials."
            )
        if self.issuer_auth_token_env == self.status_auth_token_env:
            raise PersistenceConfigurationError(
                "Issuer and status signing cannot share a KMS client "
                "credential."
            )

    def _require_remote_references(self) -> None:
        values = (
            self.issuer_key_reference,
            self.issuer_verification_method,
            self.status_key_reference,
            self.status_verification_method,
        )
        if not all(values):
            raise PersistenceConfigurationError(
                "Issuer and status KMS key references and verification "
                "methods are required."
            )
        if self.issuer_key_reference == self.status_key_reference:
            raise PersistenceConfigurationError(
                "Status lists need a signing key separate from credentials."
            )
        for method in (
            self.issuer_verification_method,
            self.status_verification_method,
        ):
            if not str(method).startswith(f"{self.issuer_did}#"):
                raise PersistenceConfigurationError(
                    "Verification methods must belong to the issuer DID."
                )


def load_signing_trust_settings(
    environ: Mapping[str, str] | None = None,
) -> SigningTrustSettings:
    values = os.environ if environ is None else environ
    environment = normalize_environment(
        values.get("IDENTITY_ENVIRONMENT", "development")
    )
    default_provider = (
        REMOTE_KMS_PROVIDER
        if is_production_like(environment)
        else LOCAL_DEVELOPMENT_PROVIDER
    )
    return SigningTrustSettings(
        environment=environment,
        provider=(
            values.get("IDENTITY_ISSUER_KEY_PROVIDER", "").strip().casefold()
            or default_provider
        ),
        issuer_did=(
            values.get("IDENTITY_ISSUER_DID", "").strip()
            or _SYNTHETIC_ISSUER_DID
        ),
        issuer_key_reference=_optional(
            values.get("IDENTITY_ISSUER_KMS_KEY_REFERENCE")
        ),
        issuer_verification_method=_optional(
            values.get("IDENTITY_ISSUER_KMS_VERIFICATION_METHOD")
        ),
        status_key_reference=_optional(
            values.get("IDENTITY_STATUS_KMS_KEY_REFERENCE")
        ),
        status_verification_method=_optional(
            values.get("IDENTITY_STATUS_KMS_VERIFICATION_METHOD")
        ),
        issuer_auth_token_env=_optional(
            values.get("IDENTITY_ISSUER_KMS_AUTH_TOKEN_ENV")
        ),
        status_auth_token_env=_optional(
            values.get("IDENTITY_STATUS_KMS_AUTH_TOKEN_ENV")
        ),
        historical_keys=_historical(
            values.get("IDENTITY_ISSUER_HISTORICAL_KEYS_JSON", "")
        ),
    )


def _optional(value: str | None) -> str | None:
    return (value or "").strip() or None


def _historical(value: str) -> tuple[HistoricalVerificationKey, ...]:
    if not value.strip():
        return ()
    try:
        decoded = json.loads(value)
        return tuple(
            HistoricalVerificationKey(
                verification_method=str(item["verificationMethod"]),
                public_key_multibase=str(item["publicKeyMultibase"]),
            )
            for item in decoded
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PersistenceConfigurationError(
            "IDENTITY_ISSUER_HISTORICAL_KEYS_JSON is invalid."
        ) from error
