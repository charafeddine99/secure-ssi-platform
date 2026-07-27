from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.persistence import (
    DuplicateEntityError,
    OptimisticLockError,
    PersistenceUnavailableError,
)
from app.domain.presentation import (
    PersistedPresentation,
    PresentationVerificationState,
)
from app.infrastructure.persistence.presentation_mapper import (
    PresentationDocumentMapper,
)


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class MongoPresentationRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._collection = collection
        self._clock = clock

    def add(
        self,
        presentation: PersistedPresentation,
    ) -> PersistedPresentation:
        if (
            presentation.version != 1
            or presentation.verification_result
            is not PresentationVerificationState.PENDING
        ):
            raise ValueError(
                "A new presentation must be pending at version 1."
            )
        try:
            self._collection.insert_one(
                PresentationDocumentMapper.to_document(presentation)
            )
        except DuplicateKeyError as error:
            raise DuplicateEntityError(
                "Presentation id or challenge/domain is already in use."
            ) from error
        except PyMongoError as error:
            raise _unavailable("presentation insertion") from error
        return presentation

    def get(
        self,
        presentation_id: str,
    ) -> PersistedPresentation | None:
        try:
            document = self._collection.find_one(
                {"presentationId": presentation_id}
            )
        except PyMongoError as error:
            raise _unavailable("presentation lookup") from error
        return (
            None
            if document is None
            else PresentationDocumentMapper.from_document(document)
        )

    def claim_verification(
        self,
        presentation_id: str,
        *,
        expected_version: int,
    ) -> PersistedPresentation | None:
        claimed_at = self._clock()
        try:
            result = self._collection.update_one(
                {
                    "presentationId": presentation_id,
                    "verificationResult": (
                        PresentationVerificationState.PENDING.value
                    ),
                    "version": expected_version,
                },
                {
                    "$set": {
                        "verificationResult": (
                            PresentationVerificationState.PROCESSING.value
                        ),
                        "updatedAt": claimed_at,
                        "processingStartedAt": claimed_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("presentation claim") from error
        if result.matched_count != 1:
            return None
        return self.get(presentation_id)

    def complete_verification(
        self,
        presentation_id: str,
        *,
        result: PresentationVerificationState,
        rejection_codes: tuple[str, ...],
        expected_version: int,
    ) -> PersistedPresentation:
        if result not in {
            PresentationVerificationState.VERIFIED,
            PresentationVerificationState.REJECTED,
        }:
            raise ValueError("Presentation completion state is invalid.")
        if (result is PresentationVerificationState.VERIFIED) == bool(
            rejection_codes
        ):
            raise ValueError("Presentation completion result is inconsistent.")
        verified_at = self._clock()
        try:
            write = self._collection.update_one(
                {
                    "presentationId": presentation_id,
                    "verificationResult": (
                        PresentationVerificationState.PROCESSING.value
                    ),
                    "version": expected_version,
                },
                {
                    "$set": {
                        "verificationResult": result.value,
                        "verifiedAt": verified_at,
                        "rejectionCodes": list(rejection_codes),
                        "updatedAt": verified_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("presentation completion") from error
        if write.matched_count != 1:
            raise OptimisticLockError(
                "Presentation verification state changed concurrently."
            )
        completed = self.get(presentation_id)
        if completed is None:
            raise _unavailable("presentation completion readback")
        return completed

    def list_stale_processing(
        self,
        *,
        started_before: datetime,
        limit: int,
    ) -> tuple[PersistedPresentation, ...]:
        if not 1 <= limit <= 500:
            raise ValueError(
                "Presentation reconciliation limit is invalid."
            )
        try:
            cursor = (
                self._collection.find(
                    {
                        "verificationResult": (
                            PresentationVerificationState.PROCESSING.value
                        ),
                        "processingStartedAt": {"$lte": started_before},
                    }
                )
                .sort("processingStartedAt", ASCENDING)
                .limit(limit)
            )
            return tuple(
                PresentationDocumentMapper.from_document(document)
                for document in cursor
            )
        except PyMongoError as error:
            raise _unavailable("stale presentation listing") from error

    def claim_reconciliation(
        self,
        presentation_id: str,
        *,
        started_before: datetime,
        reconciled_at: datetime,
        expected_version: int,
    ) -> PersistedPresentation | None:
        try:
            result = self._collection.update_one(
                {
                    "presentationId": presentation_id,
                    "verificationResult": (
                        PresentationVerificationState.PROCESSING.value
                    ),
                    "processingStartedAt": {"$lte": started_before},
                    "version": expected_version,
                },
                {
                    "$set": {
                        "lastReconciledAt": reconciled_at,
                        "updatedAt": reconciled_at,
                    },
                    "$inc": {
                        "reconciliationAttempts": 1,
                        "version": 1,
                    },
                },
            )
        except PyMongoError as error:
            raise _unavailable("presentation reconciliation claim") from error
        if result.matched_count != 1:
            return None
        return self.get(presentation_id)


def _unavailable(operation: str) -> PersistenceUnavailableError:
    return PersistenceUnavailableError(
        f"MongoDB {operation} could not be completed."
    )
