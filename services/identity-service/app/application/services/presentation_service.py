import asyncio
import copy
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from app.application.ports.canonicalizer import CredentialCanonicalizer
from app.application.ports.holder_wallet import HolderWalletRepository
from app.application.ports.presentation import (
    HolderKeyMetadataProvider,
    PresentationRepository,
)
from app.application.ports.repositories import CredentialRepository
from app.application.ports.status_list_repositories import (
    CredentialStatusEntryRepository,
)
from app.application.services.audit_outbox_service import (
    AuditOutboxDeliveryService,
)
from app.application.services.credential_proof_service import (
    CredentialProofService,
)
from app.application.services.holder_wallet_service import (
    HolderWalletService,
    PresentationChallengeService,
)
from app.application.services.internal_metrics import InternalMetrics
from app.application.services.presentation_proof_service import (
    PresentationBuilder,
    PresentationValidator,
)
from app.config.status_list_settings import StatusListSettings
from app.config.holder_wallet_settings import HolderWalletSettings
from app.domain.audit_outbox import (
    AuditOutboxRecord,
    AuditOutboxSource,
)
from app.domain.credential_status import CredentialStatus
from app.domain.holder_wallet import HolderOwnershipError
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    DuplicateEntityError,
    PersistedCredential,
    RepositoryError,
)
from app.domain.presentation import (
    PersistedPresentation,
    PresentationCredentialError,
    PresentationError,
    PresentationNotFoundError,
    PresentationReplayError,
    PresentationValidationResult,
    PresentationVerificationState,
)
from app.domain.presentation_challenge import (
    PresentationChallengeError,
)


Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]
_LOGGER = logging.getLogger(__name__)


class _PresentationCredentialInspector:
    def __init__(
        self,
        *,
        credential_repository: CredentialRepository,
        entry_repository: CredentialStatusEntryRepository,
        credential_proof_service: CredentialProofService,
        canonicalizer: CredentialCanonicalizer,
        status_list_settings: StatusListSettings,
    ) -> None:
        self._credentials = credential_repository
        self._entries = entry_repository
        self._proofs = credential_proof_service
        self._canonicalizer = canonicalizer
        self._settings = status_list_settings

    def get_by_id(
        self,
        credential_id: str,
    ) -> PersistedCredential | None:
        return self._credentials.get_by_credential_id(credential_id)

    def require_for_creation(
        self,
        credential_ids: Sequence[str],
        *,
        now: datetime,
        expected_holder: str | None = None,
        expected_wallet_id: str | None = None,
        expected_owner_user_id: str | None = None,
    ) -> tuple[PersistedCredential, ...]:
        records: list[PersistedCredential] = []
        for credential_id in credential_ids:
            credential = self._credentials.get_by_credential_id(
                credential_id
            )
            errors = self.inspect(
                credential,
                expected_document=None,
                expected_holder=None,
                now=now,
            )
            if errors:
                raise PresentationCredentialError(
                    "A referenced credential cannot be presented."
                )
            if credential is None:
                raise PresentationCredentialError(
                    "A referenced credential does not exist."
                )
            records.append(credential)
        holder_ids = {record.holder_did for record in records}
        if len(holder_ids) != 1:
            raise PresentationCredentialError(
                "All presented credentials must bind to one holder."
            )
        if expected_holder is not None and holder_ids != {expected_holder}:
            raise HolderOwnershipError(
                "A credential belongs to a different holder DID."
            )
        if expected_wallet_id is not None and any(
            record.wallet_id != expected_wallet_id
            for record in records
        ):
            raise HolderOwnershipError(
                "A credential is not available to this wallet."
            )
        if expected_owner_user_id is not None and any(
            record.owner_user_id != expected_owner_user_id
            for record in records
        ):
            raise HolderOwnershipError(
                "A credential belongs to a different user."
            )
        return tuple(records)

    def inspect(
        self,
        credential: PersistedCredential | None,
        *,
        expected_document: Mapping[str, Any] | None,
        expected_holder: str | None,
        now: datetime,
    ) -> tuple[str, ...]:
        if credential is None:
            return ("CREDENTIAL_NOT_FOUND",)
        errors: list[str] = []
        if credential.status is CredentialStatus.REVOKED:
            errors.append("CREDENTIAL_REVOKED")
        elif credential.status is CredentialStatus.SUSPENDED:
            errors.append("CREDENTIAL_SUSPENDED")
        elif credential.status is CredentialStatus.EXPIRED:
            errors.append("CREDENTIAL_EXPIRED")
        elif credential.status is not CredentialStatus.ACTIVE:
            errors.append("CREDENTIAL_NOT_ACTIVE")
        if (
            credential.expiration_date is not None
            and now > credential.expiration_date
        ):
            errors.append("CREDENTIAL_EXPIRED")
        if now < credential.issuance_date:
            errors.append("CREDENTIAL_NOT_YET_VALID")
        if (
            expected_holder is not None
            and credential.holder_did != expected_holder
        ):
            errors.append("HOLDER_BINDING_MISMATCH")
        raw = credential.raw_credential
        if raw is None:
            errors.append("CREDENTIAL_DOCUMENT_UNAVAILABLE")
            return tuple(dict.fromkeys(errors))
        try:
            persisted_digest = self._canonicalizer.calculate_digest(raw).hex()
        except Exception:
            errors.append("CREDENTIAL_NOT_CANONICALIZABLE")
        else:
            if persisted_digest != credential.credential_hash:
                errors.append("CREDENTIAL_STORAGE_INTEGRITY_FAILED")
        if expected_document is not None:
            try:
                presented_digest = self._canonicalizer.calculate_digest(
                    expected_document
                ).hex()
            except Exception:
                errors.append("CREDENTIAL_NOT_CANONICALIZABLE")
            else:
                if presented_digest != credential.credential_hash:
                    errors.append("CREDENTIAL_CONTENT_MISMATCH")
        proof_result = self._proofs.verify_credential(raw, verified_at=now)
        if not proof_result.verified:
            errors.append("CREDENTIAL_PROOF_INVALID")
        subject = raw.get("credentialSubject")
        if (
            not isinstance(subject, dict)
            or subject.get("id") != credential.holder_did
        ):
            errors.append("CREDENTIAL_HOLDER_BINDING_INVALID")
        entry = self._entries.get_by_credential_id(
            credential.credential_id
        )
        if entry is None:
            errors.append("CREDENTIAL_STATUS_ENTRY_MISSING")
        else:
            expected_status = dict(
                entry.to_credential_status(
                    status_list_credential_url=(
                        f"{self._settings.public_base_url}/"
                        f"{entry.status_list_id}"
                    )
                )
            )
            if raw.get("credentialStatus") != expected_status:
                errors.append("CREDENTIAL_STATUS_ENTRY_INVALID")
            if (
                credential.status_list_id != entry.status_list_id
                or credential.status_list_index
                != entry.status_list_index
                or credential.status_entry_id != entry.id
            ):
                errors.append("CREDENTIAL_STATUS_MAPPING_MISMATCH")
        return tuple(dict.fromkeys(errors))


class _PresentationAudit:
    def __init__(
        self,
        *,
        delivery: AuditOutboxDeliveryService,
    ) -> None:
        self._delivery = delivery

    def record(
        self,
        event_type: AuditEventType,
        *,
        presentation: PersistedPresentation,
        actor_id: str,
        correlation_id: str,
        occurred_at: datetime,
    ) -> None:
        event = AuditEvent(
            id=_audit_event_id(
                event_type,
                presentation.presentation_id,
            ),
            event_type=event_type,
            subject_id=presentation.presentation_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            metadata={
                "domain": presentation.domain,
                "itemCount": str(len(presentation.credential_ids)),
                "outcome": presentation.verification_result.value,
            },
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        try:
            self._delivery.ensure(
                AuditOutboxRecord.pending(
                    event=event,
                    aggregate_type="presentation",
                    aggregate_id=presentation.presentation_id,
                    source=AuditOutboxSource.COLLECTION,
                )
            )
            self._delivery.deliver_event(event.id)
        except RepositoryError:
            pass


class HolderPresentationService:
    def __init__(
        self,
        *,
        repository: PresentationRepository,
        credential_inspector: _PresentationCredentialInspector,
        builder: PresentationBuilder,
        audit_delivery_service: AuditOutboxDeliveryService,
        clock: Clock,
        id_generator: IdGenerator,
        wallet_service: HolderWalletService | None = None,
        challenge_service: PresentationChallengeService | None = None,
    ) -> None:
        self._repository = repository
        self._credentials = credential_inspector
        self._builder = builder
        self._audit = _PresentationAudit(
            delivery=audit_delivery_service
        )
        self._clock = clock
        self._id_generator = id_generator
        self._wallets = wallet_service
        self._challenges = challenge_service

    def create(
        self,
        credential_ids: Sequence[str],
        *,
        challenge: str | None,
        domain: str | None,
        lifetime_seconds: int,
        actor_id: str,
        correlation_id: str,
        wallet_id: str | None = None,
        challenge_id: str | None = None,
        audience: str | None = None,
    ) -> PersistedPresentation:
        now = self._clock().astimezone(UTC).replace(microsecond=0)
        secure_flow = (
            self._wallets is not None and self._challenges is not None
        )
        wallet = None
        consumed_challenge = None
        supplied_challenge = challenge
        supplied_domain = domain
        supplied_audience = audience
        if secure_flow:
            if wallet_id is None or challenge_id is None:
                raise PresentationCredentialError(
                    "A wallet and server-issued challenge are required."
                )
            wallet = self._wallets.require_owned_active(
                wallet_id,
                owner_user_id=actor_id,
                correlation_id=correlation_id,
            )
            try:
                records = self._credentials.require_for_creation(
                    credential_ids,
                    now=now,
                    expected_holder=wallet.holder_did,
                    expected_wallet_id=wallet.wallet_id,
                    expected_owner_user_id=wallet.owner_user_id,
                )
            except HolderOwnershipError:
                self._wallets.record_ownership_rejection(
                    wallet_id=wallet.wallet_id,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    reason="CREDENTIAL_NOT_OWNED",
                )
                raise
            consumed_challenge = (
                self._challenges.consume_for_presentation(
                    challenge_id,
                    wallet=wallet,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                )
            )
            binding_conflict = (
                (
                    supplied_challenge is not None
                    and supplied_challenge
                    != consumed_challenge.challenge
                )
                or (
                    supplied_domain is not None
                    and supplied_domain != consumed_challenge.domain
                )
                or (
                    supplied_audience is not None
                    and supplied_audience
                    != consumed_challenge.audience
                )
            )
            if binding_conflict:
                self._challenges.reject_binding(
                    consumed_challenge,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    reason="CHALLENGE_BINDING_MISMATCH",
                )
            challenge = consumed_challenge.challenge
            domain = consumed_challenge.domain
            audience = consumed_challenge.audience
            remaining = int(
                (consumed_challenge.expires_at - now).total_seconds()
            )
            lifetime_seconds = min(lifetime_seconds, remaining)
            if lifetime_seconds < 30:
                raise PresentationCredentialError(
                    "The challenge expires too soon for a presentation."
                )
            holder_did = wallet.holder_did
        else:
            if challenge is None or domain is None:
                raise PresentationCredentialError(
                    "Challenge and domain are required."
                )
            records = self._credentials.require_for_creation(
                credential_ids,
                now=now,
            )
            holder_did = records[0].holder_did
        documents = [
            copy.deepcopy(dict(record.raw_credential))
            for record in records
            if record.raw_credential is not None
        ]
        document = self._builder.build(
            documents,
            holder_did=holder_did,
            challenge=challenge,
            domain=domain,
            created_at=now,
            lifetime_seconds=lifetime_seconds,
            audience=audience,
            key_reference=(
                None if wallet is None else wallet.key_reference
            ),
        )
        expires_at = datetime.fromisoformat(
            document["validUntil"].replace("Z", "+00:00")
        )
        presentation = PersistedPresentation(
            id=self._id_generator(),
            presentation_id=document["id"],
            holder_did=holder_did,
            challenge=challenge,
            domain=domain,
            credential_ids=tuple(credential_ids),
            document=document,
            verification_result=PresentationVerificationState.PENDING,
            created_at=now,
            expires_at=expires_at,
            updated_at=now,
            wallet_id=None if wallet is None else wallet.wallet_id,
            owner_user_id=(
                None if wallet is None else wallet.owner_user_id
            ),
            challenge_id=(
                None
                if consumed_challenge is None
                else consumed_challenge.challenge_id
            ),
            audience=audience,
        )
        try:
            persisted = self._repository.add(presentation)
        except DuplicateEntityError as error:
            raise PresentationReplayError(
                "The challenge/domain pair was already used."
            ) from error
        self._audit.record(
            AuditEventType.PRESENTATION_CREATED,
            presentation=persisted,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=now,
        )
        return persisted

    def get(
        self,
        presentation_id: str,
        *,
        actor_id: str | None = None,
    ) -> PersistedPresentation:
        presentation = self._repository.get(presentation_id)
        if presentation is None:
            raise PresentationNotFoundError(
                "The requested presentation does not exist."
            )
        if presentation.owner_user_id is not None:
            if actor_id is None:
                raise PresentationNotFoundError(
                    "The requested presentation does not exist."
                )
            allowed = presentation.owner_user_id == actor_id
            if (
                not allowed
                and self._challenges is not None
                and presentation.challenge_id is not None
            ):
                try:
                    self._challenges.get_authorized(
                        presentation.challenge_id,
                        actor_id=actor_id,
                    )
                except PresentationChallengeError:
                    pass
                else:
                    allowed = True
            if not allowed:
                raise PresentationNotFoundError(
                    "The requested presentation does not exist."
                )
        return presentation


class VerifierPresentationService:
    def __init__(
        self,
        *,
        repository: PresentationRepository,
        credential_inspector: _PresentationCredentialInspector,
        validator: PresentationValidator,
        canonicalizer: CredentialCanonicalizer,
        audit_delivery_service: AuditOutboxDeliveryService,
        clock: Clock,
        challenge_service: PresentationChallengeService | None = None,
    ) -> None:
        self._repository = repository
        self._credentials = credential_inspector
        self._validator = validator
        self._canonicalizer = canonicalizer
        self._audit = _PresentationAudit(
            delivery=audit_delivery_service
        )
        self._clock = clock
        self._challenges = challenge_service

    def verify(
        self,
        document: Mapping[str, Any],
        *,
        expected_challenge: str | None,
        expected_domain: str | None,
        actor_id: str,
        correlation_id: str,
        expected_audience: str | None = None,
    ) -> PresentationValidationResult:
        presentation_id = document.get("id")
        if not isinstance(presentation_id, str):
            raise PresentationNotFoundError(
                "The presentation id is missing."
            )
        persisted = self._repository.get(presentation_id)
        if persisted is None:
            raise PresentationNotFoundError(
                "The requested presentation does not exist."
            )
        challenge_record = None
        if (
            self._challenges is not None
            and persisted.challenge_id is not None
        ):
            challenge_record = (
                self._challenges.require_for_verification(
                    persisted.challenge_id,
                    issued_by=actor_id,
                    holder_did=persisted.holder_did,
                )
            )
            expected_challenge = challenge_record.challenge
            expected_domain = challenge_record.domain
            expected_audience = challenge_record.audience
        if expected_challenge is None or expected_domain is None:
            raise PresentationNotFoundError(
                "Presentation challenge evidence is unavailable."
            )
        claimed = self._repository.claim_verification(
            presentation_id,
            expected_version=persisted.version,
        )
        if claimed is None:
            raise PresentationReplayError(
                "The presentation verification nonce was already consumed."
            )
        now = self._clock().astimezone(UTC).replace(microsecond=0)
        return self.complete_claimed(
            claimed,
            document=document,
            expected_challenge=expected_challenge,
            expected_domain=expected_domain,
            expected_audience=expected_audience,
            actor_id=actor_id,
            correlation_id=correlation_id,
            completed_at=now,
        )

    def complete_claimed(
        self,
        claimed: PersistedPresentation,
        *,
        document: Mapping[str, Any],
        expected_challenge: str,
        expected_domain: str,
        expected_audience: str | None,
        actor_id: str,
        correlation_id: str,
        completed_at: datetime,
    ) -> PresentationValidationResult:
        validation = self._validator.validate(
            document,
            expected_challenge=expected_challenge,
            expected_domain=expected_domain,
            expected_audience=expected_audience,
            verified_at=completed_at,
        )
        errors = list(validation.errors)
        try:
            supplied_digest = self._canonicalizer.calculate_digest(
                document
            )
            stored_digest = self._canonicalizer.calculate_digest(
                claimed.document
            )
        except Exception:
            errors.append("PRESENTATION_NOT_CANONICALIZABLE")
        else:
            if supplied_digest != stored_digest:
                errors.append("PRESENTATION_CONTENT_MISMATCH")
        if validation.credential_ids != claimed.credential_ids:
            errors.append("PRESENTATION_CREDENTIAL_SET_MISMATCH")
        if validation.holder_did != claimed.holder_did:
            errors.append("PRESENTATION_HOLDER_MISMATCH")

        presented_credentials = document.get("verifiableCredential")
        by_id = {
            item.get("id"): item
            for item in presented_credentials
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        } if isinstance(presented_credentials, list) else {}
        for credential_id in claimed.credential_ids:
            credential = self._credentials.get_by_id(
                credential_id
            )
            errors.extend(
                self._credentials.inspect(
                    credential,
                    expected_document=by_id.get(credential_id),
                    expected_holder=claimed.holder_did,
                    now=completed_at,
                )
            )
        normalized_errors = tuple(dict.fromkeys(errors))
        result_state = (
            PresentationVerificationState.REJECTED
            if normalized_errors
            else PresentationVerificationState.VERIFIED
        )
        completed = self._repository.complete_verification(
            claimed.presentation_id,
            result=result_state,
            rejection_codes=normalized_errors,
            expected_version=claimed.version,
        )
        self._audit.record(
            (
                AuditEventType.PRESENTATION_REJECTED
                if normalized_errors
                else AuditEventType.PRESENTATION_VERIFIED
            ),
            presentation=completed,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=completed.verified_at or completed_at,
        )
        return PresentationValidationResult(
            valid=not normalized_errors,
            verified_at=completed.verified_at or completed_at,
            presentation_id=completed.presentation_id,
            holder_did=completed.holder_did,
            credential_ids=completed.credential_ids,
            errors=normalized_errors,
        )


class PresentationReconciliationService:
    def __init__(
        self,
        *,
        repository: PresentationRepository,
        verifier_service: VerifierPresentationService,
        challenge_service: PresentationChallengeService,
        audit_delivery_service: AuditOutboxDeliveryService,
        settings: HolderWalletSettings,
        clock: Clock,
        metrics: InternalMetrics | None = None,
        wallet_repository: HolderWalletRepository | None = None,
        key_metadata_provider: HolderKeyMetadataProvider | None = None,
    ) -> None:
        self._repository = repository
        self._verifier = verifier_service
        self._challenges = challenge_service
        self._audit = _PresentationAudit(
            delivery=audit_delivery_service
        )
        self._settings = settings
        self._clock = clock
        self._metrics = metrics
        self._wallets = wallet_repository
        self._key_metadata = key_metadata_provider

    def reconcile(
        self,
        presentation_id: str,
        *,
        actor_id: str,
        correlation_id: str,
    ) -> PersistedPresentation:
        current = self._repository.get(presentation_id)
        if current is None:
            raise PresentationNotFoundError(
                "The requested presentation does not exist."
            )
        if current.verification_result in {
            PresentationVerificationState.VERIFIED,
            PresentationVerificationState.REJECTED,
        }:
            return current
        if (
            current.verification_result
            is not PresentationVerificationState.PROCESSING
        ):
            raise PresentationReplayError(
                "Only a stale processing presentation can be reconciled."
            )
        now = self._now()
        started_before = now - timedelta(
            seconds=self._settings.reconciliation_stale_seconds
        )
        claimed = self._repository.claim_reconciliation(
            presentation_id,
            started_before=started_before,
            reconciled_at=now,
            expected_version=current.version,
        )
        if claimed is None:
            latest = self._repository.get(presentation_id)
            if (
                latest is not None
                and latest.verification_result
                in {
                    PresentationVerificationState.VERIFIED,
                    PresentationVerificationState.REJECTED,
                }
            ):
                return latest
            raise PresentationReplayError(
                "The presentation is not stale or is being reconciled."
            )
        failed = False
        try:
            if claimed.challenge_id is None or claimed.audience is None:
                raise PresentationChallengeError(
                    "Presentation challenge evidence is incomplete."
                )
            if (
                self._wallets is not None
                and self._key_metadata is not None
                and claimed.wallet_id is not None
            ):
                wallet = self._wallets.get(claimed.wallet_id)
                if (
                    wallet is None
                    or wallet.owner_user_id != claimed.owner_user_id
                    or wallet.holder_did != claimed.holder_did
                ):
                    raise ValueError(
                        "Presentation wallet evidence is incomplete."
                    )
                metadata = self._key_metadata.get_metadata(
                    wallet.key_reference
                )
                if metadata.holder_did != claimed.holder_did:
                    raise ValueError(
                        "Presentation holder key evidence is inconsistent."
                    )
            challenge = self._challenges.get_for_reconciliation(
                claimed.challenge_id,
                holder_did=claimed.holder_did,
            )
            if challenge.expires_at <= now:
                raise PresentationChallengeError(
                    "Presentation challenge evidence has expired."
                )
            self._verifier.complete_claimed(
                claimed,
                document=claimed.document,
                expected_challenge=challenge.challenge,
                expected_domain=challenge.domain,
                expected_audience=challenge.audience,
                actor_id=actor_id,
                correlation_id=correlation_id,
                completed_at=now,
            )
        except (PresentationChallengeError, ValueError):
            failed = True
            completed = self._repository.complete_verification(
                presentation_id,
                result=PresentationVerificationState.REJECTED,
                rejection_codes=(
                    "RECONCILIATION_EVIDENCE_INCOMPLETE",
                ),
                expected_version=claimed.version,
            )
            self._audit.record(
                AuditEventType.PRESENTATION_REJECTED,
                presentation=completed,
                actor_id=actor_id,
                correlation_id=correlation_id,
                occurred_at=completed.verified_at or now,
            )
        completed = self._repository.get(presentation_id)
        if completed is None:
            raise PresentationNotFoundError(
                "The reconciled presentation could not be read."
            )
        self._audit.record(
            (
                AuditEventType.PRESENTATION_RECONCILIATION_FAILED
                if failed
                else AuditEventType.PRESENTATION_RECONCILED
            ),
            presentation=completed,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=completed.verified_at or now,
        )
        if self._metrics is not None:
            self._metrics.record_reconciliation_result(
                succeeded=not failed
            )
        return completed

    def reconcile_stale(self) -> tuple[int, int]:
        now = self._now()
        started_before = now - timedelta(
            seconds=self._settings.reconciliation_stale_seconds
        )
        stale = self._repository.list_stale_processing(
            started_before=started_before,
            limit=self._settings.reconciliation_batch_size,
        )
        succeeded = 0
        failed = 0
        for presentation in stale:
            try:
                result = self.reconcile(
                    presentation.presentation_id,
                    actor_id="system:reconciliation-worker",
                    correlation_id=(
                        f"reconcile:{presentation.presentation_id}"
                    ),
                )
                if (
                    result.rejection_codes
                    == ("RECONCILIATION_EVIDENCE_INCOMPLETE",)
                ):
                    failed += 1
                else:
                    succeeded += 1
            except (PresentationError, RepositoryError):
                failed += 1
                if self._metrics is not None:
                    self._metrics.record_reconciliation_result(
                        succeeded=False
                    )
                _LOGGER.exception(
                    "Presentation reconciliation failed safely."
                )
        if self._metrics is not None:
            self._metrics.observe_stale_processing(
                count=len(stale),
            )
        return succeeded, failed

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC).replace(microsecond=0)


class PresentationReconciliationBackgroundService:
    def __init__(
        self,
        service: PresentationReconciliationService,
        *,
        settings: HolderWalletSettings,
    ) -> None:
        self._service = service
        self._settings = settings

    async def run(self, stop_event: asyncio.Event) -> None:
        interval = self._settings.reconciliation_poll_interval_ms / 1_000
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(self._service.reconcile_stale)
            except RepositoryError:
                _LOGGER.exception(
                    "Presentation reconciliation cycle failed."
                )
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval,
                )
            except TimeoutError:
                continue


def build_credential_inspector(
    *,
    credential_repository: CredentialRepository,
    entry_repository: CredentialStatusEntryRepository,
    credential_proof_service: CredentialProofService,
    canonicalizer: CredentialCanonicalizer,
    status_list_settings: StatusListSettings,
) -> _PresentationCredentialInspector:
    return _PresentationCredentialInspector(
        credential_repository=credential_repository,
        entry_repository=entry_repository,
        credential_proof_service=credential_proof_service,
        canonicalizer=canonicalizer,
        status_list_settings=status_list_settings,
    )


def _audit_event_id(
    event_type: AuditEventType,
    presentation_id: str,
) -> str:
    value = f"{event_type.value}\0{presentation_id}".encode("utf-8")
    return sha256(value).hexdigest()[:24]
