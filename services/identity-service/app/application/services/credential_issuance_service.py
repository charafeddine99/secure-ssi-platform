import copy
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.canonicalizer import CredentialCanonicalizer
from app.application.ports.holder_wallet import HolderWalletRepository
from app.application.ports.issuance import (
    CredentialIssuanceRepository,
    IssuerCredentialSigningService,
)
from app.application.ports.status_list_repositories import (
    CredentialStatusEntryRepository,
)
from app.application.services.internal_metrics import InternalMetrics
from app.config.status_list_settings import StatusListSettings
from app.domain.bitstring_status_list import (
    CredentialStatusEntry,
    StatusListCapacityError,
    StatusPurpose,
    deterministic_index_candidate,
    generate_status_list_id,
    status_list_sequence,
)
from app.domain.credential_status import CredentialStatus
from app.domain.exceptions import ExistingProofError, UnknownIssuerError
from app.domain.issuance import (
    CredentialAlreadyIssuedError,
    IssuanceStatusSlotConflictError,
    IssuanceValidationError,
)
from app.domain.persistence import PersistedCredential
from app.services.credential_validator import CredentialProfileValidator


Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


class CredentialIssuanceService:
    """Binds status, proof, and persistence at the issuance boundary."""

    def __init__(
        self,
        *,
        validator: CredentialProfileValidator,
        signer: IssuerCredentialSigningService,
        issuance_repository: CredentialIssuanceRepository,
        entry_repository: CredentialStatusEntryRepository,
        canonicalizer: CredentialCanonicalizer,
        settings: StatusListSettings,
        clock: Clock,
        id_generator: IdGenerator,
        metrics: InternalMetrics | None = None,
        wallet_repository: HolderWalletRepository | None = None,
    ) -> None:
        self._validator = validator
        self._signer = signer
        self._issuance = issuance_repository
        self._entries = entry_repository
        self._canonicalizer = canonicalizer
        self._settings = settings
        self._clock = clock
        self._id_generator = id_generator
        self._metrics = metrics
        self._wallets = wallet_repository

    def issue(
        self,
        unsigned_credential: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            return self._issue(unsigned_credential)
        except Exception:
            if self._metrics is not None:
                self._metrics.record_issuance_failure()
            raise

    def _issue(
        self,
        unsigned_credential: Mapping[str, Any],
    ) -> dict[str, Any]:
        if "proof" in unsigned_credential:
            raise ExistingProofError(
                "The credential already contains a proof and cannot be re-signed."
            )
        if "credentialStatus" in unsigned_credential:
            raise IssuanceValidationError(
                "credentialStatus is assigned only by the issuer."
            )
        validated = self._validator.validate(
            unsigned_credential,
            require_proof=False,
        )
        issuer_did = validated["issuer"]
        if not self._signer.supports_issuer(issuer_did):
            raise UnknownIssuerError(
                "The issuer is not supported by the configured signer."
            )
        credential_id = validated["id"]
        if self._entries.get_by_credential_id(credential_id) is not None:
            raise CredentialAlreadyIssuedError(
                "Credential has already been issued."
            )

        identifiers = self._entries.list_status_list_ids(
            issuer_did,
            status_purpose=StatusPurpose.REVOCATION,
        )
        sequence = (
            status_list_sequence(identifiers[-1]) if identifiers else 1
        )
        issued_at = self._clock()
        while sequence <= 999_999:
            status_list_id = generate_status_list_id(
                issuer_did,
                sequence=sequence,
            )
            assigned = self._entries.list_by_status_list(
                status_list_id,
                limit=self._settings.capacity,
            )
            occupied_indices = {
                entry.status_list_index for entry in assigned
            }
            if len(assigned) >= self._settings.capacity:
                sequence += 1
                self._record_rollover()
                continue
            candidate = deterministic_index_candidate(
                credential_id,
                list_length=self._settings.capacity,
            )
            for offset in range(self._settings.capacity):
                status_list_index = (
                    candidate + offset
                ) % self._settings.capacity
                if status_list_index in occupied_indices:
                    continue
                entry = CredentialStatusEntry(
                    id=self._id_generator(),
                    credential_id=credential_id,
                    issuer_did=issuer_did,
                    status_list_id=status_list_id,
                    status_list_index=status_list_index,
                    status_purpose=StatusPurpose.REVOCATION,
                    created_at=issued_at,
                    updated_at=issued_at,
                )
                secured = copy.deepcopy(validated)
                secured["credentialStatus"] = dict(
                    entry.to_credential_status(
                        status_list_credential_url=self.status_list_url(
                            status_list_id
                        )
                    )
                )
                signed = self._signer.sign(secured, created=issued_at)
                persisted = self._to_persisted_credential(
                    signed,
                    entry=entry,
                    issued_at=issued_at,
                )
                try:
                    self._issuance.issue(
                        persisted,
                        status_entry=entry,
                    )
                except IssuanceStatusSlotConflictError:
                    continue
                if self._metrics is not None:
                    self._metrics.record_issuance_success(
                        occurred_at=issued_at
                    )
                    self._metrics.observe_utilization(
                        status_list_id=status_list_id,
                        assigned_entries=len(assigned) + 1,
                        capacity=self._settings.capacity,
                    )
                return signed
            sequence += 1
            self._record_rollover()
        raise StatusListCapacityError(
            "No status-list sequence remains for this issuer."
        )

    def status_list_url(self, status_list_id: str) -> str:
        return (
            f"{self._settings.public_base_url.rstrip('/')}/"
            f"{status_list_id}"
        )

    def _to_persisted_credential(
        self,
        signed: Mapping[str, Any],
        *,
        entry: CredentialStatusEntry,
        issued_at: datetime,
    ) -> PersistedCredential:
        subject = signed["credentialSubject"]
        if not isinstance(subject, dict):
            raise IssuanceValidationError(
                "Credential subject cannot be persisted."
            )
        credential_types = signed["type"]
        if not isinstance(credential_types, list):
            raise IssuanceValidationError(
                "Credential types cannot be persisted."
            )
        holder_did = subject["id"]
        wallet = (
            None
            if self._wallets is None
            else self._wallets.get_by_holder_did(holder_did)
        )
        return PersistedCredential(
            id=self._id_generator(),
            credential_id=signed["id"],
            issuer_did=signed["issuer"],
            holder_did=holder_did,
            credential_type=tuple(credential_types),
            issuance_date=_parse_timestamp(signed["validFrom"]),
            expiration_date=_parse_timestamp(signed["validUntil"]),
            credential_hash=self._canonicalizer.calculate_digest(
                signed
            ).hex(),
            status=CredentialStatus.ACTIVE,
            raw_credential=copy.deepcopy(dict(signed)),
            created_at=issued_at,
            updated_at=issued_at,
            status_list_id=entry.status_list_id,
            status_list_index=entry.status_list_index,
            status_entry_id=entry.id,
            wallet_id=None if wallet is None else wallet.wallet_id,
            owner_user_id=(
                None if wallet is None else wallet.owner_user_id
            ),
        )

    def _record_rollover(self) -> None:
        if self._metrics is not None:
            self._metrics.record_rollover()


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise IssuanceValidationError(
            "Credential timestamp cannot be persisted."
        )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise IssuanceValidationError(
            "Credential timestamp cannot be persisted."
        ) from error
