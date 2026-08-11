from datetime import datetime
from typing import Protocol

from app.domain.managed_key import (
    KeyAlgorithm,
    KeyPurpose,
    ManagedKey,
    ManagedKeyState,
    ProviderKeyMetadata,
)


class ExternalKeyProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def production_ready(self) -> bool: ...

    def create_key(
        self,
        *,
        key_id: str,
        algorithm: KeyAlgorithm,
        purpose: KeyPurpose,
        idempotency_key: str,
    ) -> ProviderKeyMetadata: ...

    def get_key_metadata(
        self,
        provider_key_reference: str,
    ) -> ProviderKeyMetadata: ...

    def sign(
        self,
        message: bytes,
        *,
        provider_key_reference: str,
        algorithm: KeyAlgorithm,
    ) -> bytes: ...

    def enable_key(self, provider_key_reference: str) -> None: ...

    def suspend_key(self, provider_key_reference: str) -> None: ...

    def revoke_key(self, provider_key_reference: str) -> None: ...

    def schedule_deletion(
        self,
        provider_key_reference: str,
        *,
        delete_at: datetime,
    ) -> None: ...

    def cancel_scheduled_deletion(
        self,
        provider_key_reference: str,
    ) -> None: ...

    def destroy_key(self, provider_key_reference: str) -> None: ...

    def is_available(self) -> bool: ...


class ManagedKeyRepository(Protocol):
    def add(self, key: ManagedKey) -> ManagedKey: ...

    def get(self, key_id: str) -> ManagedKey | None: ...

    def get_by_provider_reference(
        self,
        *,
        provider: str,
        provider_key_reference: str,
    ) -> ManagedKey | None: ...

    def get_by_verification_method(
        self,
        verification_method: str,
    ) -> ManagedKey | None: ...

    def get_by_idempotency_hash(
        self,
        *,
        wallet_id: str,
        purpose: KeyPurpose,
        idempotency_key_hash: str,
    ) -> ManagedKey | None: ...

    def get_active(
        self,
        *,
        wallet_id: str,
        purpose: KeyPurpose,
    ) -> ManagedKey | None: ...

    def list_for_wallet(
        self,
        wallet_id: str,
        *,
        limit: int = 100,
        after_key_id: str | None = None,
    ) -> tuple[ManagedKey, ...]: ...

    def list_versions(
        self,
        *,
        wallet_id: str,
        purpose: KeyPurpose,
    ) -> tuple[ManagedKey, ...]: ...

    def update(
        self,
        key: ManagedKey,
        *,
        expected_version: int,
    ) -> ManagedKey: ...

    def claim_rotation(
        self,
        key_id: str,
        *,
        rotated_at: datetime,
        expected_version: int,
    ) -> ManagedKey: ...

    def link_successor(
        self,
        key_id: str,
        *,
        successor_key_id: str,
        updated_at: datetime,
        expected_version: int,
    ) -> ManagedKey: ...

    def claim_reconciliation(
        self,
        key_id: str,
        *,
        now: datetime,
        lease_until: datetime,
        expected_version: int,
    ) -> ManagedKey | None: ...

    def list_reconciliation_candidates(
        self,
        *,
        stale_before: datetime,
        due_before: datetime,
        limit: int,
    ) -> tuple[ManagedKey, ...]: ...

    def count_by_state(self) -> dict[ManagedKeyState, int]: ...

    def count_active_by_provider_purpose(self) -> dict[str, int]: ...


class KeyPolicyProvider(Protocol):
    def require_provision_allowed(
        self,
        *,
        provider: str,
        algorithm: KeyAlgorithm,
        purpose: KeyPurpose,
    ) -> None: ...

    def require_resume_allowed(self, key: ManagedKey) -> None: ...

    def destruction_time(self, *, now: datetime) -> datetime: ...

    @property
    def rotation_grace_seconds(self) -> int: ...


class InitialWalletKeyProvisioner(Protocol):
    def provision_initial_wallet_key(
        self,
        *,
        wallet_id: str,
        owner_user_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ManagedKey: ...
