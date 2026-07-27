from datetime import datetime
from typing import Protocol

from app.domain.crypto import SigningKeyHandle, VerificationKey
from app.domain.holder_wallet import HolderKeyMetadata
from app.domain.presentation import (
    PersistedPresentation,
    PresentationVerificationState,
)


class HolderKeyProvider(Protocol):
    def provision(self, key_reference: str) -> HolderKeyMetadata: ...

    def supports_holder(self, holder_did: str) -> bool: ...

    def get_signing_key(self, holder_did: str) -> SigningKeyHandle: ...

    def get_verification_key(
        self,
        verification_method: str,
    ) -> VerificationKey: ...


class HolderSigner(Protocol):
    def sign(
        self,
        message: bytes,
        *,
        key_reference: str,
    ) -> bytes: ...


class HolderKeyMetadataProvider(Protocol):
    def get_metadata(self, key_reference: str) -> HolderKeyMetadata: ...

    def get_verification_key(
        self,
        verification_method: str,
    ) -> VerificationKey: ...


class PresentationRepository(Protocol):
    def add(
        self,
        presentation: PersistedPresentation,
    ) -> PersistedPresentation: ...

    def get(
        self,
        presentation_id: str,
    ) -> PersistedPresentation | None: ...

    def claim_verification(
        self,
        presentation_id: str,
        *,
        expected_version: int,
    ) -> PersistedPresentation | None: ...

    def complete_verification(
        self,
        presentation_id: str,
        *,
        result: PresentationVerificationState,
        rejection_codes: tuple[str, ...],
        expected_version: int,
    ) -> PersistedPresentation: ...

    def list_stale_processing(
        self,
        *,
        started_before: datetime,
        limit: int,
    ) -> tuple[PersistedPresentation, ...]: ...

    def claim_reconciliation(
        self,
        presentation_id: str,
        *,
        started_before: datetime,
        reconciled_at: datetime,
        expected_version: int,
    ) -> PersistedPresentation | None: ...
