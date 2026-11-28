"""Chooses the signing keys for this process, once, at startup.

Development modules are imported inside the development branches on purpose:
a production-like process never loads repository-derivable key material.
"""

from dataclasses import dataclass
from typing import Any

from app.application.ports.key_provider import KeyProvider
from app.config.environment_policy import is_production_like
from app.config.key_management_settings import KeyManagementSettings
from app.config.signing_trust_settings import (
    LOCAL_DEVELOPMENT_PROVIDER,
    SigningTrustSettings,
)
from app.domain.crypto import SigningKeyHandle, VerificationKey
from app.domain.exceptions import (
    UnknownIssuerError,
    UnknownVerificationMethodError,
)
from app.domain.persistence import PersistenceConfigurationError
from app.infrastructure.key_management.generic_remote_kms import (
    EnvironmentBearerAuthentication,
    GenericRemoteKmsAdapter,
    NoProviderAuthentication,
    UrllibKmsHttpTransport,
)
from app.infrastructure.key_management.remote_issuer_key_provider import (
    RemoteKmsIssuerKeyProvider,
    public_key_from_multibase,
)


@dataclass(frozen=True)
class SigningTrust:
    credential_provider: KeyProvider
    status_provider: KeyProvider
    uses_development_keys: bool


def build_remote_adapter(
    settings: KeyManagementSettings,
    *,
    token_environment_variable: str | None,
    client_purpose: str | None = None,
) -> GenericRemoteKmsAdapter:
    return GenericRemoteKmsAdapter(
        name=settings.remote_provider_name,
        base_url=settings.remote_base_url or "",
        transport=UrllibKmsHttpTransport(
            tls_verify=settings.tls_verify,
            client_certificate_path=settings.client_certificate_path,
            client_key_path=settings.client_key_path,
        ),
        authentication=(
            NoProviderAuthentication()
            if token_environment_variable is None
            else EnvironmentBearerAuthentication(token_environment_variable)
        ),
        request_timeout_seconds=settings.request_timeout_seconds,
        retry_count=settings.retry_count,
        retry_backoff_ms=settings.retry_backoff_ms,
        circuit_failure_threshold=settings.circuit_failure_threshold,
        circuit_reset_seconds=settings.circuit_reset_seconds,
        client_purpose=client_purpose,
        mutual_tls=bool(settings.client_certificate_path),
    )


def build_signing_trust(
    settings: SigningTrustSettings,
    key_settings: KeyManagementSettings,
) -> SigningTrust:
    if settings.provider == LOCAL_DEVELOPMENT_PROVIDER:
        from app.infrastructure.crypto.local_issuer_key_provider import (
            LocalIssuerKeyProvider,
        )

        local = LocalIssuerKeyProvider()
        return SigningTrust(local, local, uses_development_keys=True)
    if not key_settings.remote_base_url:
        raise PersistenceConfigurationError(
            "Issuer signing needs a configured remote KMS endpoint."
        )
    historical = {
        key.verification_method: public_key_from_multibase(
            key.public_key_multibase
        )
        for key in settings.historical_keys
    }
    credential = RemoteKmsIssuerKeyProvider(
        kms=build_remote_adapter(
            key_settings,
            token_environment_variable=settings.issuer_auth_token_env,
            client_purpose="issuer-credential-signing",
        ),
        purpose="issuer-credential-signing",
        issuer_did=settings.issuer_did,
        key_reference=settings.issuer_key_reference or "",
        verification_method=settings.issuer_verification_method or "",
        trusted_public_keys=historical,
    )
    status = RemoteKmsIssuerKeyProvider(
        kms=build_remote_adapter(
            key_settings,
            token_environment_variable=settings.status_auth_token_env,
            client_purpose="status-list-signing",
        ),
        purpose="status-list-signing",
        issuer_did=settings.issuer_did,
        key_reference=settings.status_key_reference or "",
        verification_method=settings.status_verification_method or "",
        trusted_public_keys=historical,
    )
    credential.trust_peer(status)
    status.trust_peer(credential)
    return SigningTrust(credential, status, uses_development_keys=False)


class DisabledLegacyHolderKeys:
    """Stands in for the legacy development holder keys in production-like
    processes. Every lookup fails, so a legacy wallet cannot sign or verify."""

    holder_did = ""
    verification_method = ""

    def supports_holder(self, holder_did: str) -> bool:
        del holder_did
        return False

    def get_signing_key(self, holder_did: str) -> SigningKeyHandle:
        del holder_did
        raise UnknownIssuerError("Legacy holder keys are disabled.")

    def get_verification_key(
        self,
        verification_method: str,
    ) -> VerificationKey:
        del verification_method
        raise UnknownVerificationMethodError(
            "Legacy holder keys are disabled."
        )

    def provision(self, key_reference: str) -> Any:
        del key_reference
        raise PersistenceConfigurationError(
            "Legacy holder keys are disabled."
        )

    def get_metadata(self, key_reference: str) -> Any:
        del key_reference
        raise PersistenceConfigurationError(
            "Legacy holder keys are disabled."
        )

    def sign(self, message: bytes, *, key_reference: str) -> bytes:
        del message, key_reference
        raise PersistenceConfigurationError(
            "Legacy holder keys are disabled."
        )


def build_legacy_holder_keys(environment: str) -> tuple[Any, Any]:
    if is_production_like(environment):
        disabled = DisabledLegacyHolderKeys()
        return disabled, disabled
    from app.infrastructure.crypto.local_holder_key_provider import (
        LocalDevelopmentHolderSigner,
        LocalHolderKeyProvider,
    )

    provider = LocalHolderKeyProvider()
    return provider, LocalDevelopmentHolderSigner(provider)
