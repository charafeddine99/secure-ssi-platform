from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from threading import Lock

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.ports.managed_keys import ManagedKeyRecoveryOutcome
from app.application.ports.repositories import RecoveryRepository
from app.application.services.metrics import RecoveryMetrics
from app.application.services.recovery_service import RecoveryService
from app.core.config import load_settings
from app.domain.auth import RecoveryPrincipal
from app.domain.recovery import RecoveryNotFoundError, RecoveryReason
from app.infrastructure.persistence.memory_repository import (
    MemoryRecoveryRepository,
)
from app.infrastructure.secret_sharing.pycryptodome_provider import (
    PyCryptodomeSecretSharingProvider,
)


NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
OWNER = "usr_local_holder"
WALLET_ID = "wallet_abcdefghijklmnop"


class MutableClock:
    def __init__(self) -> None:
        self.value = NOW
        self._lock = Lock()

    def __call__(self) -> datetime:
        with self._lock:
            return self.value

    def advance(self, **values: int) -> None:
        with self._lock:
            self.value += timedelta(**values)


class Sequence:
    def __init__(self) -> None:
        self._values: dict[str, int] = {}
        self._lock = Lock()

    def __call__(self, prefix: str) -> str:
        with self._lock:
            value = self._values.get(prefix, 0) + 1
            self._values[prefix] = value
        return f"{prefix}_{value:016d}"


class FakeManagedKeyGateway:
    def __init__(self) -> None:
        self.owners = {WALLET_ID: OWNER}
        self.outcomes: dict[str, ManagedKeyRecoveryOutcome] = {}
        self.fail = False
        self.calls = 0
        self.disabled_keys: set[str] = set()
        self.active_key = "key_0000000000000001"
        self.active_did = "did:key:zOldRecoveryPublicKeyMaterial"

    def verify_wallet_owner(self, *, wallet_id: str, owner_user_id: str) -> None:
        if self.owners.get(wallet_id) != owner_user_id:
            raise RecoveryNotFoundError("Wallet was not found.")

    def rotate_for_recovery(
        self,
        *,
        request_id: str,
        wallet_id: str,
        owner_user_id: str,
        reason: RecoveryReason,
    ) -> ManagedKeyRecoveryOutcome:
        self.verify_wallet_owner(wallet_id=wallet_id, owner_user_id=owner_user_id)
        existing = self.outcomes.get(request_id)
        if existing is not None:
            return existing
        self.calls += 1
        if self.fail:
            raise RuntimeError("injected provider failure")
        predecessor_key = self.active_key
        predecessor_did = self.active_did
        suffix = sha256(request_id.encode()).hexdigest()[:24]
        self.active_key = f"key_{suffix}"
        self.active_did = f"did:key:z{suffix}"
        self.disabled_keys.add(predecessor_key)
        outcome = ManagedKeyRecoveryOutcome(
            predecessor_key_id=predecessor_key,
            successor_key_id=self.active_key,
            predecessor_did=predecessor_did,
            successor_did=self.active_did,
            provider="development",
        )
        self.outcomes[request_id] = outcome
        return outcome

    def sign(self, key_id: str, payload: bytes) -> bytes:
        if key_id in self.disabled_keys or key_id != self.active_key:
            raise RuntimeError("key cannot sign")
        return sha256(key_id.encode() + payload).digest()

    @staticmethod
    def verify(key_id: str, payload: bytes, signature: bytes) -> bool:
        return signature == sha256(key_id.encode() + payload).digest()


@dataclass
class TestRuntime:
    service: RecoveryService
    repository: RecoveryRepository
    gateway: FakeManagedKeyGateway
    metrics: RecoveryMetrics
    clock: MutableClock
    owner: RecoveryPrincipal
    admin: RecoveryPrincipal
    guardians: tuple[RecoveryPrincipal, ...]
    guardian_dids: dict[str, str]
    guardian_signing_keys: dict[str, Ed25519PrivateKey]

    def sign_decision(
        self,
        *,
        guardian_id: str,
        request_id: str,
        challenge: str,
        decision: str = "APPROVE",
    ) -> str:
        guardian = self.repository.get_guardian(guardian_id)
        request = self.repository.get_request(request_id)
        if guardian is None or request is None:
            raise AssertionError("Guardian and recovery request must exist in test runtime")
        key = self.guardian_signing_keys[guardian.guardian_user_id]
        issued_at = int(self.clock().timestamp())
        return jwt.encode(
            {
                "iss": guardian.guardian_did,
                "sub": guardian.guardian_id,
                "aud": "secure-ssi-platform:guardian-recovery",
                "requestId": request.request_id,
                "sessionId": request.session.session_id,
                "walletId": request.wallet_id,
                "decision": decision,
                "challenge": challenge,
                "iat": issued_at,
                "exp": issued_at + 120,
                "jti": token_urlsafe(18),
            },
            key,
            algorithm="EdDSA",
            headers={
                "typ": "guardian-recovery+jwt",
                "kid": guardian.verification_method,
            },
        )


def build_runtime(repository: RecoveryRepository | None = None) -> TestRuntime:
    repository = repository or MemoryRecoveryRepository()
    gateway = FakeManagedKeyGateway()
    metrics = RecoveryMetrics()
    clock = MutableClock()
    settings = load_settings({})
    service = RecoveryService(
        repository=repository,
        secret_sharing=PyCryptodomeSecretSharingProvider(b"R" * 32),
        managed_keys=gateway,
        settings=settings,
        metrics=metrics,
        clock=clock,
        id_generator=Sequence(),
        worker_id="worker_recovery_test",
    )
    owner = RecoveryPrincipal.from_claims(OWNER, ("holder",))
    admin = RecoveryPrincipal.from_claims("usr_local_admin", ("admin",))
    guardians = tuple(
        RecoveryPrincipal.from_claims(f"usr_guardian_{index}", ("holder",))
        for index in range(1, 8)
    )
    guardian_signing_keys = {
        guardian.user_id: Ed25519PrivateKey.from_private_bytes(
            sha256(f"recovery-test-guardian:{guardian.user_id}".encode()).digest()
        )
        for guardian in guardians
    }
    guardian_dids = {
        guardian.user_id: _did_key(guardian_signing_keys[guardian.user_id])
        for guardian in guardians
    }
    runtime = TestRuntime(
        service=service,
        repository=repository,
        gateway=gateway,
        metrics=metrics,
        clock=clock,
        owner=owner,
        admin=admin,
        guardians=guardians,
        guardian_dids=guardian_dids,
        guardian_signing_keys=guardian_signing_keys,
    )
    # State-machine tests exercise the real verifier while keeping each test
    # focused on its scenario; API tests pass explicit request proofs.
    approve = service.approve
    reject = service.reject

    def approve_with_test_proof(
        principal: RecoveryPrincipal,
        request_id: str,
        *,
        guardian_id: str,
        challenge: str,
        proof: str | None = None,
    ):
        proof = proof or runtime.sign_decision(
            guardian_id=guardian_id,
            request_id=request_id,
            challenge=challenge,
            decision="APPROVE",
        )
        return approve(
            principal,
            request_id,
            guardian_id=guardian_id,
            challenge=challenge,
            proof=proof,
        )

    def reject_with_test_proof(
        principal: RecoveryPrincipal,
        request_id: str,
        *,
        guardian_id: str,
        challenge: str,
        proof: str | None = None,
    ):
        proof = proof or runtime.sign_decision(
            guardian_id=guardian_id,
            request_id=request_id,
            challenge=challenge,
            decision="REJECT",
        )
        return reject(
            principal,
            request_id,
            guardian_id=guardian_id,
            challenge=challenge,
            proof=proof,
        )

    service.approve = approve_with_test_proof  # type: ignore[method-assign]
    service.reject = reject_with_test_proof  # type: ignore[method-assign]
    return runtime


def configure_guardians(
    runtime: TestRuntime,
    *,
    count: int = 5,
    threshold: int = 3,
    time_lock_seconds: int = 10,
) -> tuple[str, ...]:
    runtime.service.put_policy(
        runtime.owner,
        wallet_id=WALLET_ID,
        minimum_approvals=threshold,
        maximum_guardians=count,
        approval_window_seconds=300,
        time_lock_seconds=time_lock_seconds,
        recovery_expiration_seconds=1200,
        maximum_attempts=3,
        cooldown_seconds=0,
        allow_cancellation=True,
    )
    ids = []
    for index, principal in enumerate(runtime.guardians[:count], start=1):
        guardian = runtime.service.create_guardian(
            runtime.owner,
            wallet_id=WALLET_ID,
            guardian_user_id=principal.user_id,
            guardian_did=runtime.guardian_dids[principal.user_id],
            display_name=f"Guardian {index}",
            verification_method=(
                f"{runtime.guardian_dids[principal.user_id]}#"
                f"{runtime.guardian_dids[principal.user_id][len('did:key:'):]}"
            ),
        )
        ids.append(guardian.guardian_id)
    return tuple(ids)


def _did_key(private_key: Ed25519PrivateKey) -> str:
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "did:key:z" + _encode_base58_btc(b"\xed\x01" + public_key)


def _encode_base58_btc(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    leading_zeroes = len(value) - len(value.lstrip(b"\x00"))
    return "1" * leading_zeroes + (encoded or ("1" if not leading_zeroes else ""))
