from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.application.services.revocation_ledger_service import (
    RevocationLedgerService,
)
from app.domain.credential_status import CredentialStatus
from app.domain.persistence import PersistenceUnavailableError
from app.domain.revocation_ledger import (
    EVENT_REVOKED,
    SOURCE_BACKFILL,
)


@dataclass(frozen=True)
class ReconciliationResult:
    backfilled: int
    records_repaired: int


class RevocationReconciliationService:
    """Makes records and the ledger agree, always towards "revoked".

    Runs before the service reports ready, so a restored older snapshot cannot
    bring a revoked credential back.
    """

    def __init__(
        self,
        *,
        ledger: RevocationLedgerService,
        credentials: Collection[dict[str, Any]],
        clock: Callable[[], datetime],
    ) -> None:
        self._ledger = ledger
        self._credentials = credentials
        self._clock = clock

    def reconcile(self) -> ReconciliationResult:
        self._ledger.assert_intact()
        return ReconciliationResult(
            backfilled=self._backfill_ledger(),
            records_repaired=self._repair_records(),
        )

    def _backfill_ledger(self) -> int:
        known = {
            (event.status_list_id, event.status_list_index)
            for event in self._ledger.ordered_events()
        }
        added = 0
        try:
            documents = list(
                self._credentials.find(
                    {"status": CredentialStatus.REVOKED.value}
                )
            )
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                "Credential records are unavailable."
            ) from error
        for document in documents:
            list_id = document.get("statusListId")
            index = document.get("statusListIndex")
            if not isinstance(list_id, str) or not isinstance(index, int):
                continue
            if (list_id, index) in known:
                continue
            self._ledger.record_revocation(
                credential_id=str(document["credentialId"]),
                issuer_did=str(document.get("issuerDid", "")),
                status_list_id=list_id,
                status_list_index=index,
                status_purpose="revocation",
                reason=str(document.get("revocationReason", "")),
                actor=str(document.get("revokedBy", "system:backfill")),
                correlation_id="revocation-ledger-backfill",
                source=SOURCE_BACKFILL,
            )
            added += 1
        return added

    def _repair_records(self) -> int:
        repaired = 0
        now = self._clock().astimezone(UTC)
        for event in self._ledger.ordered_events():
            if event.event_type != EVENT_REVOKED:
                continue
            try:
                result = self._credentials.update_one(
                    {
                        "credentialId": event.credential_id,
                        "status": {"$ne": CredentialStatus.REVOKED.value},
                    },
                    {
                        "$set": {
                            "status": CredentialStatus.REVOKED.value,
                            "revokedAt": datetime.fromisoformat(
                                event.occurred_at
                            ),
                            "revokedBy": event.actor,
                            "statusListId": event.status_list_id,
                            "statusListIndex": event.status_list_index,
                            "updatedAt": now,
                        },
                        "$inc": {"version": 1},
                    },
                )
            except PyMongoError as error:
                raise PersistenceUnavailableError(
                    "Credential records are unavailable."
                ) from error
            repaired += result.matched_count
        return repaired
