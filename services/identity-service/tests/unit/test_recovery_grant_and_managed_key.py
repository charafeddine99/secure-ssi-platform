from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.config.recovery_grant_settings import load_recovery_grant_settings
from app.domain.exceptions import AuthConfigurationError
from app.domain.managed_key import ManagedKeyState
from app.infrastructure.auth.recovery_grant import (
    RecoveryGrantError,
    RecoveryGrantVerifier,
)
from tests.unit.test_managed_key_service import OWNER, WALLET_ID, Runtime


def _grant(
    *, scope: str = "managed-key:recover", lifetime_seconds: int = 60
) -> tuple[str, datetime]:
    settings = load_recovery_grant_settings({})
    now = datetime.now(UTC).replace(microsecond=0)
    token = jwt.encode(
        {
            "iss": settings.issuer,
            "sub": OWNER,
            "aud": settings.audience,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=lifetime_seconds)).timestamp()),
            "jti": "recovery-grant-test-jti",
            "scope": scope,
            "wallet_id": WALLET_ID,
            "request_id": "recovery_0000000000000001",
        },
        settings.secret,
        algorithm="HS256",
    )
    return token, now


def test_recovery_grant_is_short_lived_and_context_bound() -> None:
    settings = load_recovery_grant_settings({})
    verifier = RecoveryGrantVerifier(settings)
    token, now = _grant()
    claims = verifier.verify(
        token,
        scope="managed-key:recover",
        wallet_id=WALLET_ID,
        owner_user_id=OWNER,
        request_id="recovery_0000000000000001",
        checked_at=now,
    )

    assert claims.owner_user_id == OWNER
    assert settings.secret not in repr(verifier)
    with pytest.raises(RecoveryGrantError):
        verifier.verify(
            token,
            scope="wallet:ownership:read",
            wallet_id=WALLET_ID,
            owner_user_id=OWNER,
            checked_at=now,
        )
    with pytest.raises(RecoveryGrantError):
        verifier.verify(
            token,
            scope="managed-key:recover",
            wallet_id="wallet_foreignabcdefghij",
            owner_user_id=OWNER,
            request_id="recovery_0000000000000001",
            checked_at=now,
        )
    long_lived, _ = _grant(lifetime_seconds=settings.lifetime_seconds + 1)
    with pytest.raises(RecoveryGrantError):
        verifier.verify(
            long_lived,
            scope="managed-key:recover",
            wallet_id=WALLET_ID,
            owner_user_id=OWNER,
            request_id="recovery_0000000000000001",
            checked_at=now,
        )


def test_recovery_grant_configuration_rejects_malformed_integer() -> None:
    with pytest.raises(AuthConfigurationError):
        load_recovery_grant_settings(
            {"IDENTITY_RECOVERY_GRANT_LIFETIME_SECONDS": "not-an-integer"}
        )


def test_managed_key_recovery_rotates_idempotently_and_disables_predecessor() -> None:
    runtime = Runtime()
    predecessor = runtime.create()
    signer = runtime.signer()
    payload = b"historic recovery proof"
    signature = signer.sign(
        payload, key_reference=predecessor.provider_key_reference or ""
    )
    verification_key = signer.get_verification_key(
        predecessor.verification_method or ""
    )

    source, successor = runtime.service.recover_wallet(
        WALLET_ID,
        owner_user_id=OWNER,
        recovery_request_id="recovery_0000000000000001",
        reason="ACCOUNT_COMPROMISE",
        correlation_id="recovery_0000000000000001",
    )
    repeated_source, repeated_successor = runtime.service.recover_wallet(
        WALLET_ID,
        owner_user_id=OWNER,
        recovery_request_id="recovery_0000000000000001",
        reason="ACCOUNT_COMPROMISE",
        correlation_id="recovery_0000000000000001",
    )
    stored_source = runtime.keys.get(predecessor.key_id)

    assert source.key_id == predecessor.key_id
    assert repeated_source.key_id == predecessor.key_id
    assert repeated_successor == successor
    assert successor.holder_did != predecessor.holder_did
    assert stored_source is not None
    assert stored_source.state is ManagedKeyState.COMPROMISED
    with pytest.raises(Exception):
        signer.sign(
            b"must fail", key_reference=predecessor.provider_key_reference or ""
        )
    Ed25519PublicKey.from_public_bytes(
        verification_key.public_key_bytes
    ).verify(signature, payload)
    new_signature = signer.sign(
        payload, key_reference=successor.provider_key_reference or ""
    )
    successor_verification = signer.get_verification_key(
        successor.verification_method or ""
    )
    Ed25519PublicKey.from_public_bytes(
        successor_verification.public_key_bytes
    ).verify(new_signature, payload)


def test_account_compromise_retry_reconciles_a_partial_rotation() -> None:
    runtime = Runtime()
    predecessor = runtime.create()
    request_id = "recovery_0000000000000002"
    runtime.service.recover_wallet(
        WALLET_ID,
        owner_user_id=OWNER,
        recovery_request_id=request_id,
        reason="KEY_LOSS",
        correlation_id=request_id,
    )
    after_rotation = runtime.keys.get(predecessor.key_id)
    assert after_rotation is not None
    assert after_rotation.state is ManagedKeyState.SUSPENDED

    reconciled_predecessor, successor = runtime.service.recover_wallet(
        WALLET_ID,
        owner_user_id=OWNER,
        recovery_request_id=request_id,
        reason="ACCOUNT_COMPROMISE",
        correlation_id=request_id,
    )
    repeated_predecessor, repeated_successor = runtime.service.recover_wallet(
        WALLET_ID,
        owner_user_id=OWNER,
        recovery_request_id=request_id,
        reason="ACCOUNT_COMPROMISE",
        correlation_id=request_id,
    )

    assert reconciled_predecessor.state is ManagedKeyState.COMPROMISED
    assert repeated_predecessor.state is ManagedKeyState.COMPROMISED
    assert repeated_successor == successor
