"""WP-29 P0-1: production-like gates and the remote issuer signing contract.

FakeKms below is a contract-test double. It is not a live KMS and proves nothing
about any real provider.
"""

import hashlib
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config.environment_policy import is_production_like
from app.config.key_management_settings import (
    KeyManagementSettings,
    load_key_management_settings,
)
from app.config.signing_trust_settings import (
    SigningTrustSettings,
    load_signing_trust_settings,
)
from app.domain.exceptions import UnknownVerificationMethodError
from app.domain.managed_key import (
    KeyAlgorithm,
    ProviderMetadataError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.domain.persistence import PersistenceConfigurationError
from app.infrastructure.crypto.multibase import encode_base58_btc
from app.infrastructure.key_management.generic_remote_kms import (
    GenericRemoteKmsAdapter,
    KmsHttpResponse,
    NoProviderAuthentication,
)
from app.infrastructure.key_management.remote_issuer_key_provider import (
    RemoteKmsIssuerKeyProvider,
)
from app.infrastructure.key_management.signing_trust import (
    DisabledLegacyHolderKeys,
    build_legacy_holder_keys,
    build_signing_trust,
)


SERVICE_ROOT = Path(__file__).resolve().parents[2]
# Same treatment as tests/conftest.py: a native module blocked on some hosts.
NATIVE_STUB = (
    "import sys\n"
    "try:\n"
    "    import ckzg\n"
    "except ImportError:\n"
    "    from unittest.mock import MagicMock\n"
    "    sys.modules['ckzg'] = MagicMock()\n"
)
ISSUER = "did:web:issuer.acme.test"
METHOD = f"{ISSUER}#credential-2026"
STATUS_METHOD = f"{ISSUER}#status-2026"


def _multibase(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return encode_base58_btc(b"\xed\x01" + raw)


class FakeKms:
    """Holds the key on its own side of the boundary, like a real KMS would."""

    production_ready = True

    def __init__(self, method: str = METHOD) -> None:
        self._key = Ed25519PrivateKey.generate()
        self.method = method
        self.failure: Exception | None = None
        self.signature_override: bytes | None = None
        self.enabled = True
        self.signed: list[str] = []

    def is_available(self) -> bool:
        return self.failure is None

    def get_key_metadata(self, reference: str) -> SimpleNamespace:
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            enabled=self.enabled,
            destroyed=False,
            verification_method=self.method,
            public_key_multibase=_multibase(self._key),
        )

    def sign(self, message, *, provider_key_reference, algorithm) -> bytes:
        assert algorithm is KeyAlgorithm.ED25519
        if self.failure:
            raise self.failure
        self.signed.append(provider_key_reference)
        if self.signature_override is not None:
            return self.signature_override
        return self._key.sign(message)


def _provider(kms: FakeKms, **overrides) -> RemoteKmsIssuerKeyProvider:
    return RemoteKmsIssuerKeyProvider(
        kms=kms,
        purpose="issuer-credential-signing",
        issuer_did=ISSUER,
        key_reference="kms-ref-credential",
        verification_method=kms.method,
        **overrides,
    )


def _production_trust(**overrides) -> SigningTrustSettings:
    values = dict(
        environment="production",
        provider="remote-kms",
        issuer_did=ISSUER,
        issuer_key_reference="kms-ref-credential",
        issuer_verification_method=METHOD,
        status_key_reference="kms-ref-status",
        status_verification_method=STATUS_METHOD,
        issuer_auth_token_env="KMS_ISSUER_TOKEN",
        status_auth_token_env="KMS_STATUS_TOKEN",
    )
    values.update(overrides)
    return SigningTrustSettings(**values)


@pytest.mark.parametrize(
    "value",
    [
        "production", "prod", "prd", "staging", "staging2", "preprod",
        "preview", "qa", "unknown", "", "   ", "PROD", "  Production ",
        "Staging\n", "developmentx", "dev-prod",
    ],
)
def test_every_unlisted_environment_is_production_like(value: str) -> None:
    assert is_production_like(value) is True


@pytest.mark.parametrize(
    "value",
    ["development", "dev", "local", "test", "testing", " DEV ", "Testing\t"],
)
def test_only_named_environments_are_development(value: str) -> None:
    assert is_production_like(value) is False


def test_none_environment_is_production_like() -> None:
    assert is_production_like(None) is True


def test_environment_policy_is_identical_in_identity_and_recovery() -> None:
    identity = SERVICE_ROOT / "app/config/environment_policy.py"
    recovery = (
        SERVICE_ROOT.parent
        / "recovery-service/app/core/environment_policy.py"
    )
    assert identity.read_bytes() == recovery.read_bytes()


@pytest.mark.parametrize("environment", ["prd", "staging2", "preprod", "x"])
def test_development_provider_refused_in_any_production_like_environment(
    environment: str,
) -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_key_management_settings(
            {
                "IDENTITY_ENVIRONMENT": environment,
                "IDENTITY_KMS_ENABLED_PROVIDERS": "development",
            }
        )


def test_prohibit_flag_false_does_not_open_the_gate() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_key_management_settings(
            {
                "IDENTITY_ENVIRONMENT": "production",
                "IDENTITY_KMS_ENABLED_PROVIDERS": "development",
                "IDENTITY_KMS_PROHIBIT_DEVELOPMENT_IN_PRODUCTION": "false",
            }
        )


def test_mixed_holder_providers_are_refused_in_production() -> None:
    with pytest.raises(PersistenceConfigurationError):
        KeyManagementSettings(
            environment="production",
            enabled_providers=("remote-kms", "development"),
            default_provider="remote-kms",
            remote_base_url="https://kms.example.test",
            remote_auth_token_env="KMS_TOKEN",
        )


def test_remote_kms_without_client_identity_is_refused_in_production() -> None:
    with pytest.raises(PersistenceConfigurationError):
        KeyManagementSettings(
            environment="production",
            enabled_providers=("remote-kms",),
            default_provider="remote-kms",
            remote_base_url="https://kms.example.test",
        )


def test_production_issuer_defaults_to_kms_and_needs_references() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_signing_trust_settings({"IDENTITY_ENVIRONMENT": "production"})


def test_production_cannot_select_the_local_issuer_provider() -> None:
    with pytest.raises(PersistenceConfigurationError):
        _production_trust(provider="local-development")


def test_production_cannot_use_the_synthetic_issuer_identity() -> None:
    with pytest.raises(PersistenceConfigurationError):
        _production_trust(
            issuer_did="did:web:issuer.example",
            issuer_verification_method="did:web:issuer.example#a",
            status_verification_method="did:web:issuer.example#b",
        )


def test_status_key_must_differ_from_credential_key() -> None:
    with pytest.raises(PersistenceConfigurationError):
        _production_trust(status_key_reference="kms-ref-credential")


def test_issuer_and_status_clients_cannot_share_a_credential() -> None:
    with pytest.raises(PersistenceConfigurationError):
        _production_trust(status_auth_token_env="KMS_ISSUER_TOKEN")


def test_verification_method_must_belong_to_the_issuer() -> None:
    with pytest.raises(PersistenceConfigurationError):
        _production_trust(issuer_verification_method="did:web:evil.test#k")


def test_remote_trust_needs_a_kms_endpoint() -> None:
    with pytest.raises(PersistenceConfigurationError):
        build_signing_trust(_production_trust(), KeyManagementSettings())


@pytest.mark.parametrize(
    "module_call",
    [
        "from app.infrastructure.crypto.local_issuer_key_provider import "
        "LocalIssuerKeyProvider; LocalIssuerKeyProvider()",
        "import app.infrastructure.crypto.local_holder_key_provider",
        "import app.infrastructure.key_management.development_provider",
    ],
)
def test_development_key_sources_refuse_to_load_in_production(
    module_call: str,
) -> None:
    result = subprocess.run(
        [sys.executable, "-c", module_call],
        cwd=SERVICE_ROOT,
        env={**os.environ, "IDENTITY_ENVIRONMENT": "production"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "not available in production-like" in result.stderr


def test_production_process_stops_at_startup_without_kms() -> None:
    result = subprocess.run(
        [sys.executable, "-c", NATIVE_STUB + "import app.api.v1.dependencies"],
        cwd=SERVICE_ROOT,
        env={
            **os.environ,
            "IDENTITY_ENVIRONMENT": "production",
            "IDENTITY_AUTH_JWT_SECRET": "x" * 40,
            "IDENTITY_AUTH_FIXTURE_USERS_ENABLED": "false",
            "IDENTITY_KMS_ENABLED_PROVIDERS": "remote-kms",
            "IDENTITY_KMS_DEFAULT_PROVIDER": "remote-kms",
            "IDENTITY_KMS_REMOTE_BASE_URL": "https://kms.example.test",
            "IDENTITY_KMS_REMOTE_AUTH_TOKEN_ENV": "T",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "PersistenceConfigurationError" in result.stderr or (
        "ConfigurationError" in result.stderr
    )
    assert "x" * 40 not in result.stderr


def test_production_process_loads_no_development_key_module() -> None:
    script = NATIVE_STUB + (
        "import app.api.v1.dependencies\n"
        "bad=[m for m in sys.modules if m.endswith(("
        "'local_issuer_key_provider','local_holder_key_provider',"
        "'key_management.development_provider'))]\n"
        "print('LOADED',bad)\n"
        "assert not bad\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=SERVICE_ROOT,
        env={
            **os.environ,
            "IDENTITY_ENVIRONMENT": "production",
            "IDENTITY_AUTH_JWT_SECRET": "x" * 40,
            "IDENTITY_AUTH_FIXTURE_USERS_ENABLED": "false",
            "IDENTITY_AUTH_USER_PROVIDER": "mongodb",
            "IDENTITY_RECOVERY_GRANT_SECRET": "y" * 40,
            "IDENTITY_FRAUD_SERVICE_TOKEN": "z" * 40,
            "IDENTITY_KMS_ENABLED_PROVIDERS": "remote-kms",
            "IDENTITY_KMS_DEFAULT_PROVIDER": "remote-kms",
            "IDENTITY_KMS_REMOTE_BASE_URL": "https://kms.example.test",
            "IDENTITY_KMS_REMOTE_AUTH_TOKEN_ENV": "T",
            "IDENTITY_ISSUER_DID": ISSUER,
            "IDENTITY_ISSUER_KMS_KEY_REFERENCE": "a",
            "IDENTITY_ISSUER_KMS_VERIFICATION_METHOD": METHOD,
            "IDENTITY_STATUS_KMS_KEY_REFERENCE": "b",
            "IDENTITY_STATUS_KMS_VERIFICATION_METHOD": STATUS_METHOD,
            "IDENTITY_ISSUER_KMS_AUTH_TOKEN_ENV": "T1",
            "IDENTITY_STATUS_KMS_AUTH_TOKEN_ENV": "T2",
            "IDENTITY_REVOCATION_LEDGER_URI": "mongodb://ledger.invalid/x",
            "IDENTITY_REVOCATION_LEDGER_MAC_KEY_BASE64": "A" * 44,
            "IDENTITY_REVOCATION_ANCHOR_PATH": "/tmp/anchor.json",
            "IDENTITY_STEP_UP_SECRET": "s" * 40,
            "IDENTITY_MFA_FACTOR_KEY_BASE64": "QUFB" * 10 + "QUE=",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    assert "LOADED []" in result.stdout


def test_legacy_holder_keys_are_disabled_in_production() -> None:
    provider, signer = build_legacy_holder_keys("prd")
    assert isinstance(provider, DisabledLegacyHolderKeys)
    assert provider.supports_holder("did:key:z") is False
    with pytest.raises(UnknownVerificationMethodError):
        provider.get_verification_key("did:key:z#z")
    with pytest.raises(PersistenceConfigurationError):
        signer.sign(b"m", key_reference="r")


def test_remote_signature_is_verifiable_and_no_key_bytes_are_exposed() -> None:
    kms = FakeKms()
    provider = _provider(kms)
    handle = provider.get_signing_key(ISSUER)
    signature = handle.sign(b"credential")
    key = provider.get_verification_key(METHOD)
    assert len(signature) == 64
    assert kms.signed == ["kms-ref-credential"]
    assert handle.verification_method == METHOD
    assert not hasattr(handle, "_private_key")
    assert "private" not in repr(provider).casefold()
    assert len(key.public_key_bytes) == 32


@pytest.mark.parametrize(
    "failure",
    [
        ProviderUnavailableError("down"),
        ProviderTimeoutError("slow"),
        ProviderMetadataError("bad"),
    ],
)
def test_kms_failure_fails_closed_without_any_fallback(failure) -> None:
    kms = FakeKms()
    kms.failure = failure
    with pytest.raises(type(failure)):
        _provider(kms).get_signing_key(ISSUER).sign(b"credential")


def test_wrong_length_signature_is_refused() -> None:
    kms = FakeKms()
    kms.signature_override = b"short"
    with pytest.raises(ProviderMetadataError):
        _provider(kms).get_signing_key(ISSUER).sign(b"credential")


def test_signature_from_another_key_is_refused() -> None:
    kms = FakeKms()
    kms.signature_override = Ed25519PrivateKey.generate().sign(b"credential")
    with pytest.raises(ProviderMetadataError):
        _provider(kms).get_signing_key(ISSUER).sign(b"credential")


def test_disabled_kms_key_is_refused() -> None:
    kms = FakeKms()
    kms.enabled = False
    with pytest.raises(ProviderMetadataError):
        _provider(kms).get_signing_key(ISSUER).sign(b"credential")


def test_metadata_for_a_different_method_is_refused() -> None:
    kms = FakeKms(method=f"{ISSUER}#other")
    provider = RemoteKmsIssuerKeyProvider(
        kms=kms,
        purpose="p",
        issuer_did=ISSUER,
        key_reference="r",
        verification_method=METHOD,
    )
    with pytest.raises(ProviderMetadataError):
        provider.get_signing_key(ISSUER).sign(b"credential")


def test_historical_key_stays_resolvable_after_rotation() -> None:
    old = Ed25519PrivateKey.generate()
    raw = old.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    historical = f"{ISSUER}#credential-2025"
    provider = _provider(FakeKms(), trusted_public_keys={historical: raw})
    assert provider.get_verification_key(historical).public_key_bytes == raw
    with pytest.raises(UnknownVerificationMethodError):
        provider.get_verification_key(f"{ISSUER}#never-existed")


def test_status_list_and_credential_signing_use_separate_kms_keys() -> None:
    credential_kms, status_kms = FakeKms(), FakeKms(STATUS_METHOD)
    credential = _provider(credential_kms)
    status = RemoteKmsIssuerKeyProvider(
        kms=status_kms,
        purpose="status-list-signing",
        issuer_did=ISSUER,
        key_reference="kms-ref-status",
        verification_method=STATUS_METHOD,
    )
    credential.trust_peer(status)
    credential.get_signing_key(ISSUER).sign(b"a")
    status.get_signing_key(ISSUER).sign(b"b")
    assert credential_kms.signed == ["kms-ref-credential"]
    assert status_kms.signed == ["kms-ref-status"]
    assert len(credential.get_verification_key(STATUS_METHOD).public_key_bytes) == 32


def test_kms_audit_records_metadata_but_no_secret_bytes(caplog) -> None:
    caplog.set_level(logging.INFO, logger="secure_ssi.kms.audit")
    kms = FakeKms()
    message = b"credential-payload-marker"
    _provider(kms).get_signing_key(ISSUER).sign(message)
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "purpose=issuer-credential-signing" in text
    assert "outcome=SIGNED" in text
    assert "kms-ref-credential" not in text
    assert "credential-payload-marker" not in text
    assert hashlib.sha256(message).hexdigest()[:16] in text


class _Transport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers: dict[str, str] = {}

    def request(self, *, method, url, headers, body, timeout_seconds):
        self.headers = headers
        return KmsHttpResponse(status=200, body=self.body)


def test_adapter_refuses_a_response_that_exports_key_material() -> None:
    adapter = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=_Transport(b'{"signature":"AA","privateKey":"AA"}'),
    )
    with pytest.raises(ProviderMetadataError):
        adapter.sign(
            b"m",
            provider_key_reference="r",
            algorithm=KeyAlgorithm.ED25519,
        )


def test_adapter_sends_freshness_and_purpose_binding() -> None:
    transport = _Transport(b'{"signature":"AA"}')
    adapter = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=transport,
        client_purpose="status-list-signing",
    )
    adapter.sign(
        b"m",
        provider_key_reference="r",
        algorithm=KeyAlgorithm.ED25519,
    )
    assert transport.headers["X-Kms-Client-Purpose"] == "status-list-signing"
    assert transport.headers["X-Request-Id"]
    stamp = datetime.fromisoformat(transport.headers["X-Request-Timestamp"])
    assert abs((datetime.now(UTC) - stamp).total_seconds()) < 60


def test_adapter_is_not_production_ready_without_client_identity() -> None:
    bare = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=_Transport(b"{}"),
        authentication=NoProviderAuthentication(),
    )
    mtls = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=_Transport(b"{}"),
        mutual_tls=True,
    )
    assert bare.production_ready is False
    assert mtls.production_ready is True


def test_adapter_refuses_plain_http() -> None:
    with pytest.raises(ValueError):
        GenericRemoteKmsAdapter(
            name="remote-kms",
            base_url="http://kms.example.test",
            transport=_Transport(b"{}"),
        )
