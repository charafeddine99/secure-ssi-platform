import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.config.key_management_settings import (
    KeyManagementSettings,
    load_key_management_settings,
)
from app.domain.managed_key import (
    InvalidKeyTransitionError,
    KeyAlgorithm,
    KeyPurpose,
    ManagedKey,
    ManagedKeySigningRejectedError,
    ManagedKeyState,
    ProviderKeyNotFoundError,
    ProviderMetadataError,
    ProviderPermissionDeniedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    validate_provider_metadata,
)
from app.domain.persistence import (
    DocumentMappingError,
    OptimisticLockError,
    PersistenceConfigurationError,
)
from app.infrastructure.key_management.development_provider import (
    DevelopmentExternalKeyProvider,
    DevelopmentProviderFailure,
)
from app.infrastructure.key_management.generic_remote_kms import (
    EnvironmentBearerAuthentication,
    GenericRemoteKmsAdapter,
    KmsHttpResponse,
)
from app.infrastructure.persistence.managed_key_mappers import (
    ManagedKeyDocumentMapper,
    reject_private_key_fields,
)
from app.infrastructure.persistence.managed_key_repository import (
    MongoManagedKeyRepository,
)
from app.infrastructure.persistence.indexes import (
    MANAGED_KEYS_COLLECTION,
    ensure_mongo_indexes,
)
from tests.support.fake_mongo import FakeCollection, FakeDatabase


NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def _active_key(
    *,
    purpose: KeyPurpose = KeyPurpose.PRESENTATION_SIGNING,
) -> tuple[ManagedKey, DevelopmentExternalKeyProvider]:
    provider = DevelopmentExternalKeyProvider()
    metadata = provider.create_key(
        key_id="key_abcdefghijklmnop",
        algorithm=KeyAlgorithm.ED25519,
        purpose=purpose,
        idempotency_key="idempotency-digest-0001",
    )
    return (
        ManagedKey(
            id="64b64c0f0123456789abcdef",
            key_id="key_abcdefghijklmnop",
            wallet_id="wallet_abcdefghijklmnop",
            owner_user_id="usr_holder",
            holder_did=metadata.holder_did,
            provider=metadata.provider,
            provider_key_reference=metadata.provider_key_reference,
            algorithm=metadata.algorithm,
            purpose=purpose,
            state=ManagedKeyState.ACTIVE,
            public_key_multibase=metadata.public_key_multibase,
            fingerprint=metadata.fingerprint,
            verification_method=metadata.verification_method,
            created_at=NOW,
            updated_at=NOW,
            activated_at=NOW,
            last_provider_sync_at=NOW,
        ),
        provider,
    )


def test_managed_key_enforces_lifecycle_and_signing_purpose() -> None:
    key, _ = _active_key()

    key.require_signing(
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        algorithm=KeyAlgorithm.ED25519,
    )
    with pytest.raises(ManagedKeySigningRejectedError):
        key.require_signing(
            purpose=KeyPurpose.CREDENTIAL_SIGNING,
            algorithm=KeyAlgorithm.ED25519,
        )
    suspended = key.transition(
        ManagedKeyState.SUSPENDED,
        at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(ManagedKeySigningRejectedError):
        suspended.require_signing(
            purpose=KeyPurpose.PRESENTATION_SIGNING,
            algorithm=KeyAlgorithm.ED25519,
        )
    assert suspended.transition(
        ManagedKeyState.ACTIVE,
        at=NOW + timedelta(seconds=2),
    ).state is ManagedKeyState.ACTIVE


def test_irreversible_lifecycle_transitions_are_explicit() -> None:
    key, _ = _active_key()
    compromised = key.transition(
        ManagedKeyState.COMPROMISED,
        at=NOW + timedelta(seconds=1),
        reason="confirmed compromise",
    )
    revoked = compromised.transition(
        ManagedKeyState.REVOKED,
        at=NOW + timedelta(seconds=2),
    )
    pending = revoked.transition(
        ManagedKeyState.DESTROY_PENDING,
        at=NOW + timedelta(seconds=3),
        destruction_scheduled_at=NOW + timedelta(hours=24),
    )
    destroyed = pending.transition(
        ManagedKeyState.DESTROYED,
        at=NOW + timedelta(hours=24),
    )

    assert destroyed.destroyed_at == NOW + timedelta(hours=24)
    with pytest.raises(InvalidKeyTransitionError):
        destroyed.transition(
            ManagedKeyState.ACTIVE,
            at=NOW + timedelta(hours=25),
        )
    with pytest.raises(InvalidKeyTransitionError):
        revoked.transition(
            ManagedKeyState.ACTIVE,
            at=NOW + timedelta(hours=1),
        )


def test_development_provider_is_idempotent_and_never_exports_private_key() -> None:
    provider = DevelopmentExternalKeyProvider()
    first = provider.create_key(
        key_id="key_abcdefghijklmnop",
        algorithm=KeyAlgorithm.ED25519,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        idempotency_key="same-request-0001",
    )
    second = provider.create_key(
        key_id="key_differentvalue0001",
        algorithm=KeyAlgorithm.ED25519,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        idempotency_key="same-request-0001",
    )
    message = b"canonical presentation payload"
    signature = provider.sign(
        message,
        provider_key_reference=first.provider_key_reference,
        algorithm=KeyAlgorithm.ED25519,
    )
    public_bytes = provider.get_public_key_bytes(
        first.provider_key_reference
    )
    Ed25519PublicKey.from_public_bytes(public_bytes).verify(
        signature,
        message,
    )

    assert first == second
    assert provider.production_ready is False
    assert not hasattr(first, "private_key")
    assert "private_material=<redacted>" in repr(provider)
    provider.suspend_key(first.provider_key_reference)
    with pytest.raises(ProviderPermissionDeniedError):
        provider.sign(
            message,
            provider_key_reference=first.provider_key_reference,
            algorithm=KeyAlgorithm.ED25519,
        )


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (DevelopmentProviderFailure.TIMEOUT, ProviderTimeoutError),
        (
            DevelopmentProviderFailure.PERMISSION_DENIED,
            ProviderPermissionDeniedError,
        ),
        (DevelopmentProviderFailure.NOT_FOUND, ProviderKeyNotFoundError),
    ],
)
def test_development_provider_maps_injected_failures(
    failure: DevelopmentProviderFailure,
    error: type[Exception],
) -> None:
    provider = DevelopmentExternalKeyProvider()
    metadata = provider.create_key(
        key_id="key_abcdefghijklmnop",
        algorithm=KeyAlgorithm.ED25519,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        idempotency_key="failure-test-0001",
    )
    provider.inject_failure(failure)

    with pytest.raises(error):
        provider.get_key_metadata(metadata.provider_key_reference)


def test_managed_key_mapper_rejects_private_fields_recursively() -> None:
    key, _ = _active_key()
    document = ManagedKeyDocumentMapper.to_document(key)

    assert document["providerKeyReference"]
    assert "privateKey" not in json.dumps(document, default=str)
    with pytest.raises(DocumentMappingError):
        reject_private_key_fields(
            {"providerMetadata": {"privateKeyJwk": {"d": "forbidden"}}}
        )
    with pytest.raises(DocumentMappingError):
        ManagedKeyDocumentMapper.from_document(
            {**document, "secretKeyMultibase": "forbidden"}
        )


def test_managed_key_repository_cas_rotation_and_cursor_listing() -> None:
    collection = FakeCollection(
        unique_fields=("keyId",),
        unique_compounds=(
            ("provider", "providerKeyReference"),
            ("walletId", "purpose", "keyVersion"),
        ),
    )
    repository = MongoManagedKeyRepository(cast(Any, collection))
    key, _ = _active_key()
    repository.add(key)

    claimed = repository.claim_rotation(
        key.key_id,
        rotated_at=NOW + timedelta(seconds=1),
        expected_version=key.version,
    )
    assert claimed.state is ManagedKeyState.ROTATING
    assert repository.get_by_provider_reference(
        provider=key.provider,
        provider_key_reference=key.provider_key_reference or "",
    ) == claimed
    assert repository.list_for_wallet(
        key.wallet_id,
        after_key_id=None,
    ) == (claimed,)
    with pytest.raises(OptimisticLockError):
        repository.claim_rotation(
            key.key_id,
            rotated_at=NOW + timedelta(seconds=2),
            expected_version=key.version,
        )


def test_key_management_settings_fail_closed_in_production() -> None:
    with pytest.raises(PersistenceConfigurationError):
        load_key_management_settings(
            {
                "IDENTITY_ENVIRONMENT": "production",
                "IDENTITY_KMS_ENABLED_PROVIDERS": "development",
            }
        )
    with pytest.raises(PersistenceConfigurationError):
        KeyManagementSettings(
            environment="production",
            enabled_providers=("remote-kms",),
            default_provider="remote-kms",
            remote_base_url="https://kms.example.test",
            tls_verify=False,
        )
    safe = KeyManagementSettings(
        environment="production",
        enabled_providers=("remote-kms",),
        default_provider="remote-kms",
        development_provider_enabled=False,
        remote_base_url="https://kms.example.test",
    )
    assert safe.default_provider == "remote-kms"


class _QueueTransport:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.requests: list[dict[str, object]] = []

    def request(self, **kwargs: object) -> KmsHttpResponse:
        self.requests.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return cast(KmsHttpResponse, outcome)


def _remote_metadata_body() -> bytes:
    provider = DevelopmentExternalKeyProvider(name="remote-kms")
    metadata = provider.create_key(
        key_id="key_abcdefghijklmnop",
        algorithm=KeyAlgorithm.ED25519,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        idempotency_key="remote-metadata-0001",
    )
    return json.dumps(
        {
            "provider": metadata.provider,
            "providerKeyReference": metadata.provider_key_reference,
            "algorithm": metadata.algorithm.value,
            "publicKeyMultibase": metadata.public_key_multibase,
            "fingerprint": metadata.fingerprint,
            "holderDid": metadata.holder_did,
            "verificationMethod": metadata.verification_method,
            "enabled": True,
        }
    ).encode()


def test_generic_remote_kms_retries_timeout_and_maps_safe_metadata() -> None:
    transport = _QueueTransport(
        [
            TimeoutError(),
            KmsHttpResponse(status=200, body=_remote_metadata_body()),
        ]
    )
    adapter = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=transport,
        retry_count=1,
        retry_backoff_ms=0,
    )

    metadata = adapter.create_key(
        key_id="key_abcdefghijklmnop",
        algorithm=KeyAlgorithm.ED25519,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        idempotency_key="remote-request-0001",
    )

    assert metadata.provider == "remote-kms"
    assert len(transport.requests) == 2
    assert transport.requests[0]["url"] == "https://kms.example.test/v1/keys"
    assert "authentication=<redacted>" in repr(adapter)


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (403, ProviderPermissionDeniedError),
        (404, ProviderKeyNotFoundError),
        (504, ProviderTimeoutError),
    ],
)
def test_generic_remote_kms_maps_stable_errors(
    status: int,
    error: type[Exception],
) -> None:
    adapter = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=_QueueTransport([KmsHttpResponse(status=status)]),
        retry_count=0,
    )

    with pytest.raises(error):
        adapter.get_key_metadata("remote-kms:key:abcdefghijklmnop")


def test_environment_authentication_never_reveals_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_REMOTE_KMS_TOKEN", "do-not-disclose")
    authentication = EnvironmentBearerAuthentication(
        "TEST_REMOTE_KMS_TOKEN"
    )

    assert authentication.headers()["Authorization"].startswith("Bearer ")
    assert "do-not-disclose" not in repr(authentication)


def test_generic_remote_signing_sends_only_public_contract_fields() -> None:
    encoded_signature = base64.urlsafe_b64encode(b"s" * 64).rstrip(b"=")
    transport = _QueueTransport(
        [
            KmsHttpResponse(
                status=200,
                body=json.dumps(
                    {"signature": encoded_signature.decode()}
                ).encode(),
            )
        ]
    )
    adapter = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=transport,
        retry_count=0,
    )

    signature = adapter.sign(
        b"canonical payload",
        provider_key_reference="remote-kms:key:abcdefghijklmnop",
        algorithm=KeyAlgorithm.ED25519,
    )
    request_body = json.loads(cast(bytes, transport.requests[0]["body"]))

    assert signature == b"s" * 64
    assert set(request_body) == {
        "algorithm",
        "payload",
        "payloadEncoding",
    }
    assert "private" not in json.dumps(request_body).casefold()


def test_generic_remote_circuit_breaker_stops_repeated_provider_calls() -> None:
    transport = _QueueTransport([KmsHttpResponse(status=503)])
    adapter = GenericRemoteKmsAdapter(
        name="remote-kms",
        base_url="https://kms.example.test",
        transport=transport,
        retry_count=0,
        circuit_failure_threshold=1,
    )

    assert adapter.is_available() is False
    with pytest.raises(ProviderUnavailableError):
        adapter.get_key_metadata("remote-kms:key:abcdefghijklmnop")
    assert len(transport.requests) == 1


def test_inconsistent_provider_metadata_is_rejected() -> None:
    provider = DevelopmentExternalKeyProvider()
    metadata = provider.create_key(
        key_id="key_abcdefghijklmnop",
        algorithm=KeyAlgorithm.ED25519,
        purpose=KeyPurpose.PRESENTATION_SIGNING,
        idempotency_key="metadata-mismatch-0001",
    )
    provider.inject_failure(
        DevelopmentProviderFailure.INCONSISTENT_METADATA
    )
    inconsistent = provider.get_key_metadata(
        metadata.provider_key_reference
    )

    with pytest.raises(ProviderMetadataError):
        validate_provider_metadata(
            inconsistent,
            provider="development",
            algorithm=KeyAlgorithm.ED25519,
        )


def test_managed_key_indexes_are_complete_and_idempotent() -> None:
    database = FakeDatabase()

    ensure_mongo_indexes(cast(Any, database))
    ensure_mongo_indexes(cast(Any, database))
    names = {
        index.document["name"]
        for index in database[MANAGED_KEYS_COLLECTION].indexes
    }

    assert {
        "uq_managed_keys_key_id",
        "uq_managed_keys_provider_reference",
        "uq_managed_keys_wallet_purpose_version",
        "uq_managed_keys_active_wallet_purpose",
        "ix_managed_keys_stale_rotation",
        "ix_managed_keys_destruction_due",
        "uq_managed_keys_idempotency",
    }.issubset(names)
