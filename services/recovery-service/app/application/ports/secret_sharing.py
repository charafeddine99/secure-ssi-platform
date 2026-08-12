from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.recovery import RecoverySecretShareMetadata


@dataclass(frozen=True)
class SecretSharingContext:
    recovery_request_id: str
    policy_id: str
    policy_version: int
    share_version: int


@dataclass(frozen=True)
class SplitSecretResult:
    commitment: str
    shares: tuple[RecoverySecretShareMetadata, ...]


class SecretSharingProvider(Protocol):
    def split(
        self,
        secret: bytes,
        *,
        threshold: int,
        guardian_ids: tuple[str, ...],
        context: SecretSharingContext,
        created_at: datetime,
    ) -> SplitSecretResult: ...

    def validate_share(
        self,
        share: RecoverySecretShareMetadata,
        *,
        context: SecretSharingContext,
    ) -> None: ...

    def combine(
        self,
        shares: tuple[RecoverySecretShareMetadata, ...],
        *,
        threshold: int,
        context: SecretSharingContext,
        expected_commitment: str,
    ) -> bytes: ...

    def validate_threshold(self, *, threshold: int, share_count: int) -> None: ...
