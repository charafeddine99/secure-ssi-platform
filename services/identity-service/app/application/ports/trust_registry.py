from __future__ import annotations

from typing import Protocol
from app.domain.trust_registry import TrustRecord, TrustStatus


class TrustRegistryRepository(Protocol):
    def add(self, record: TrustRecord) -> TrustRecord: ...

    def get_by_issuer_did(self, issuer_did: str) -> TrustRecord | None: ...

    def get_by_id(self, record_id: str) -> TrustRecord | None: ...

    def list_all(
        self,
        status: TrustStatus | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[TrustRecord]: ...

    def update(self, record: TrustRecord, expected_version: int) -> TrustRecord: ...

    def delete(self, record_id: str) -> bool: ...
