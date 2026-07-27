from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from app.domain.persistence import DuplicateEntityError
from app.domain.presentation import (
    PersistedPresentation,
    PresentationVerificationState,
)
from app.infrastructure.crypto.local_holder_key_provider import (
    LocalHolderKeyProvider,
)
from app.infrastructure.persistence.presentation_mapper import (
    PresentationDocumentMapper,
)
from app.infrastructure.persistence.presentation_repository import (
    MongoPresentationRepository,
)
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _presentation(
    *,
    storage_id: str = "64b64c0f0123456789abcdef",
    presentation_id: str = (
        "urn:uuid:00000000-0000-4000-8000-000000000001"
    ),
) -> PersistedPresentation:
    holder = LocalHolderKeyProvider().holder_did
    return PersistedPresentation(
        id=storage_id,
        presentation_id=presentation_id,
        holder_did=holder,
        challenge="challenge_nonce_00000001",
        domain="verifier.example",
        credential_ids=("urn:uuid:credential-1",),
        document={
            "id": presentation_id,
            "holder": holder,
        },
        verification_result=PresentationVerificationState.PENDING,
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        updated_at=NOW,
    )


def test_mapper_round_trip_and_repository_state_machine() -> None:
    collection = FakeCollection(
        unique_fields=("presentationId",),
        unique_compounds=(("challenge", "domain"),),
    )
    repository = MongoPresentationRepository(
        cast(Any, collection),
        clock=lambda: NOW,
    )
    presentation = _presentation()

    stored = repository.add(presentation)
    claimed = repository.claim_verification(
        stored.presentation_id,
        expected_version=1,
    )
    assert claimed is not None
    assert claimed.verification_result is (
        PresentationVerificationState.PROCESSING
    )
    assert claimed.version == 2
    assert (
        repository.claim_verification(
            stored.presentation_id,
            expected_version=2,
        )
        is None
    )

    completed = repository.complete_verification(
        stored.presentation_id,
        result=PresentationVerificationState.VERIFIED,
        rejection_codes=(),
        expected_version=2,
    )
    assert completed.verification_result is (
        PresentationVerificationState.VERIFIED
    )
    assert completed.verified_at == NOW
    assert completed.version == 3
    assert PresentationDocumentMapper.from_document(
        PresentationDocumentMapper.to_document(completed)
    ) == completed


def test_repository_enforces_unique_challenge_domain_pair() -> None:
    collection = FakeCollection(
        unique_fields=("presentationId",),
        unique_compounds=(("challenge", "domain"),),
    )
    repository = MongoPresentationRepository(cast(Any, collection))
    repository.add(_presentation())

    with pytest.raises(DuplicateEntityError):
        repository.add(
            _presentation(
                storage_id="64b64c0f0123456789abcdee",
                presentation_id=(
                    "urn:uuid:00000000-0000-4000-8000-000000000002"
                ),
            )
        )


def test_repository_claims_stale_processing_reconciliation_once() -> None:
    collection = FakeCollection(
        unique_fields=("presentationId",),
        unique_compounds=(("challenge", "domain"),),
    )
    repository = MongoPresentationRepository(
        cast(Any, collection),
        clock=lambda: NOW,
    )
    presentation = repository.add(_presentation())
    claimed = repository.claim_verification(
        presentation.presentation_id,
        expected_version=1,
    )
    assert claimed is not None

    stale = repository.list_stale_processing(
        started_before=NOW,
        limit=10,
    )
    reconciliation = repository.claim_reconciliation(
        presentation.presentation_id,
        started_before=NOW,
        reconciled_at=NOW + timedelta(seconds=1),
        expected_version=2,
    )

    assert stale == (claimed,)
    assert reconciliation is not None
    assert reconciliation.reconciliation_attempts == 1
    assert reconciliation.last_reconciled_at == NOW + timedelta(seconds=1)
    assert reconciliation.version == 3
    assert (
        repository.claim_reconciliation(
            presentation.presentation_id,
            started_before=NOW,
            reconciled_at=NOW + timedelta(seconds=2),
            expected_version=2,
        )
        is None
    )
