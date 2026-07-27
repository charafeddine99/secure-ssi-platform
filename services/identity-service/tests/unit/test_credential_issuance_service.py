import copy
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.application.services.credential_issuance_service import (
    CredentialIssuanceService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.config.status_list_settings import StatusListSettings
from app.domain.bitstring_status_list import (
    deterministic_index_candidate,
    generate_status_list_id,
)
from app.domain.issuance import CredentialAlreadyIssuedError
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.crypto.local_issuer_key_provider import (
    LocalIssuerKeyProvider,
    SYNTHETIC_ISSUER_DID,
)
from app.infrastructure.crypto.local_issuer_signing_service import (
    LocalIssuerSigningService,
)
from app.infrastructure.fixtures.signed_credentials import (
    build_local_proof_service,
    load_unsigned_credential,
)
from app.infrastructure.persistence.issuance_repository import (
    MongoCredentialIssuanceRepository,
)
from app.infrastructure.persistence.status_list_repositories import (
    MongoCredentialStatusEntryRepository,
)
from app.services.credential_validator import CredentialProfileValidator
from tests.support.fake_mongo import FakeCollection


NOW = datetime(2026, 6, 1, tzinfo=UTC)


class _IdSequence:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"{self.value:024x}"


def _runtime(
    *,
    capacity: int = 2,
    signer: Any | None = None,
) -> tuple[
    CredentialIssuanceService,
    FakeCollection,
    FakeCollection,
    InternalMetrics,
]:
    credentials = FakeCollection(
        unique_fields=("credentialId",),
        unique_compounds=(("statusListId", "statusListIndex"),),
    )
    entries = FakeCollection(
        unique_fields=("credentialId",),
        unique_compounds=(("statusListId", "statusListIndex"),),
    )
    metrics = InternalMetrics()
    service = CredentialIssuanceService(
        validator=CredentialProfileValidator(),
        signer=signer
        or LocalIssuerSigningService(
            proof_service=build_local_proof_service(),
            key_provider=LocalIssuerKeyProvider(),
        ),
        issuance_repository=MongoCredentialIssuanceRepository(
            cast(Any, credentials)
        ),
        entry_repository=MongoCredentialStatusEntryRepository(
            cast(Any, entries),
            cast(Any, credentials),
        ),
        canonicalizer=JcsCanonicalizer(),
        settings=StatusListSettings(
            public_base_url=(
                "https://issuer.example/api/v1/status-lists"
            ),
            capacity=capacity,
        ),
        clock=lambda: NOW,
        id_generator=_IdSequence(),
        metrics=metrics,
    )
    return service, credentials, entries, metrics


def _credential(number: int) -> dict[str, Any]:
    credential = load_unsigned_credential()
    credential["id"] = (
        f"urn:uuid:00000000-0000-4000-8000-{number:012d}"
    )
    return credential


def test_issuance_binds_signs_and_persists_one_atomic_document() -> None:
    service, credentials, entries, metrics = _runtime()
    unsigned = _credential(1)
    original = copy.deepcopy(unsigned)

    signed = service.issue(unsigned)
    stored = credentials.find_one({"credentialId": signed["id"]})

    assert unsigned == original
    assert stored is not None
    assert stored["rawCredential"] == signed
    assert stored["version"] == 1
    assert stored["statusEntryId"] is not None
    assert entries.documents == []
    assert signed["credentialStatus"]["statusListIndex"] == str(
        deterministic_index_candidate(signed["id"], list_length=2)
    )
    assert metrics.snapshot().issuance_succeeded == 1


def test_duplicate_issuance_is_rejected_without_partial_status_record() -> None:
    service, credentials, entries, metrics = _runtime()
    service.issue(_credential(1))

    with pytest.raises(CredentialAlreadyIssuedError):
        service.issue(_credential(1))

    assert len(credentials.documents) == 1
    assert entries.documents == []
    assert metrics.snapshot().issuance_failed == 1


def test_capacity_rolls_over_to_deterministic_next_publication() -> None:
    service, credentials, _, metrics = _runtime(capacity=2)

    first = service.issue(_credential(1))
    second = service.issue(_credential(2))
    third = service.issue(_credential(3))

    first_list = first["credentialStatus"]["statusListCredential"]
    assert second["credentialStatus"]["statusListCredential"] == first_list
    assert third["credentialStatus"]["statusListCredential"].endswith(
        f"{generate_status_list_id(SYNTHETIC_ISSUER_DID, sequence=2)}"
    )
    assert len(credentials.documents) == 3
    assert metrics.snapshot().rollover_count == 1


def test_signer_failure_never_creates_a_partial_credential() -> None:
    class FailingIssuerSigner:
        def supports_issuer(self, issuer_did: str) -> bool:
            return issuer_did == SYNTHETIC_ISSUER_DID

        def sign(
            self,
            credential: dict[str, Any],
            *,
            created: datetime,
        ) -> dict[str, Any]:
            raise RuntimeError("synthetic signer failure")

    service, credentials, entries, metrics = _runtime(
        signer=FailingIssuerSigner()
    )

    with pytest.raises(RuntimeError):
        service.issue(_credential(1))

    assert credentials.documents == []
    assert entries.documents == []
    assert metrics.snapshot().issuance_failed == 1
