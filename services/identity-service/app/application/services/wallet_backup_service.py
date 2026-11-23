"""WP-28 Holder Wallet Backup & Restore.

Custody model: holder signing keys are server-managed (ManagedKeyService), so a
wallet backup never contains key material. A backup is a server-produced,
canonical JSON payload of the holder's own stored credentials. The browser
encrypts it with a passphrase (PBKDF2-SHA256 + AES-256-GCM, WebCrypto); the
passphrase and the encrypted archive never reach this service. The service
keeps only metadata, including the SHA-256 of the exact payload, so a restore
is accepted only for an archive this wallet produced and nobody altered.

Restore never trusts the archive: every credential is re-verified (proof,
validity window, local issuer trust), its holder binding is checked against
the wallet's current DID and its revocation bit is read from the published
status list. Revoked, unverifiable or foreign credentials are never imported,
and an existing credential is never overwritten.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Any, Mapping

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.credential_status import CredentialStatus
from app.domain.holder_wallet import HolderWallet
from app.domain.persistence import (
    AuditEvent,
    AuditEventType,
    PersistedCredential,
    PersistenceUnavailableError,
)
from app.infrastructure.crypto.jcs_canonicalizer import JcsCanonicalizer
from app.infrastructure.persistence.mappers import new_object_id
from app.infrastructure.status_list_document_generator import decode_status_list_bit


BACKUP_FORMAT = "secure-ssi-wallet-backup"
BACKUP_FORMAT_VERSION = 1
MAX_BACKUP_ITEMS = 100
# JSON escaping can double the body; the API Gateway caps requests at 1 MiB.
MAX_PAYLOAD_CHARACTERS = 400_000

Clock = Callable[[], datetime]
_CANONICALIZER = JcsCanonicalizer()


class WalletBackupError(Exception):
    code = "WALLET_BACKUP_ERROR"
    status_code = 400


class WalletBackupNotFoundError(WalletBackupError):
    code = "WALLET_BACKUP_NOT_FOUND"
    status_code = 404


class WalletBackupIntegrityError(WalletBackupError):
    code = "WALLET_BACKUP_INTEGRITY_MISMATCH"
    status_code = 422


class WalletBackupConflictError(WalletBackupError):
    code = "WALLET_RESTORE_CONFLICT"
    status_code = 409


class WalletBackupTooLargeError(WalletBackupError):
    code = "WALLET_BACKUP_TOO_LARGE"
    status_code = 413


# Per-item restore classification. Only RESTORABLE items are ever written.
RESTORABLE = "RESTORABLE"
ALREADY_PRESENT = "ALREADY_PRESENT"
HELD_BY_ANOTHER_WALLET = "HELD_BY_ANOTHER_WALLET"
HOLDER_BINDING_MISMATCH = "HOLDER_BINDING_MISMATCH"
PROOF_INVALID = "PROOF_INVALID"
REVOKED = "REVOKED"
STATUS_UNVERIFIABLE = "STATUS_UNVERIFIABLE"
UNSUPPORTED_ITEM = "UNSUPPORTED_ITEM"
# Restore-job outcomes.
RESTORED = "RESTORED"
NOT_ATTEMPTED = "NOT_ATTEMPTED"


@dataclass(frozen=True)
class WalletBackupRecord:
    backup_id: str
    wallet_id: str
    owner_user_id: str
    holder_did: str
    format_version: int
    item_count: int
    content_digest: str
    created_at: datetime

    def to_document(self) -> dict[str, Any]:
        return {
            "_id": self.backup_id,
            "backupId": self.backup_id,
            "walletId": self.wallet_id,
            "ownerUserId": self.owner_user_id,
            "holderDid": self.holder_did,
            "formatVersion": self.format_version,
            "itemCount": self.item_count,
            "contentDigest": self.content_digest,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "WalletBackupRecord":
        return cls(
            backup_id=document["backupId"],
            wallet_id=document["walletId"],
            owner_user_id=document["ownerUserId"],
            holder_did=document["holderDid"],
            format_version=int(document["formatVersion"]),
            item_count=int(document["itemCount"]),
            content_digest=document["contentDigest"],
            created_at=_aware(document["createdAt"]),
        )


@dataclass(frozen=True)
class RestoreItemPlan:
    credential_id: str
    outcome: str
    credential_types: tuple[str, ...]


@dataclass(frozen=True)
class RestorePlan:
    backup: WalletBackupRecord
    items: tuple[RestoreItemPlan, ...]

    def count(self, outcome: str) -> int:
        return sum(item.outcome == outcome for item in self.items)


@dataclass(frozen=True)
class RestoreJob:
    restore_id: str
    backup_id: str
    wallet_id: str
    owner_user_id: str
    status: str
    restored: int
    already_present: int
    rejected: int
    failure_code: str | None
    items: tuple[RestoreItemPlan, ...]
    created_at: datetime

    def to_document(self, idempotency_key_hash: str) -> dict[str, Any]:
        return {
            "_id": self.restore_id,
            "restoreId": self.restore_id,
            "backupId": self.backup_id,
            "walletId": self.wallet_id,
            "ownerUserId": self.owner_user_id,
            "status": self.status,
            "restored": self.restored,
            "alreadyPresent": self.already_present,
            "rejected": self.rejected,
            "failureCode": self.failure_code,
            "items": [
                {
                    "credentialId": item.credential_id,
                    "outcome": item.outcome,
                    "credentialTypes": list(item.credential_types),
                }
                for item in self.items
            ],
            "idempotencyKeyHash": idempotency_key_hash,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "RestoreJob":
        return cls(
            restore_id=document["restoreId"],
            backup_id=document["backupId"],
            wallet_id=document["walletId"],
            owner_user_id=document["ownerUserId"],
            status=document["status"],
            restored=int(document["restored"]),
            already_present=int(document["alreadyPresent"]),
            rejected=int(document["rejected"]),
            failure_code=document.get("failureCode"),
            items=tuple(
                RestoreItemPlan(
                    credential_id=item["credentialId"],
                    outcome=item["outcome"],
                    credential_types=tuple(item.get("credentialTypes") or ()),
                )
                for item in document.get("items") or ()
            ),
            created_at=_aware(document["createdAt"]),
        )


class WalletBackupService:
    def __init__(
        self,
        *,
        wallets: Any,
        credentials: Any,
        status_lists: Any,
        proof_service: Any,
        audits: Any,
        backups: Collection[dict[str, Any]],
        restore_jobs: Collection[dict[str, Any]],
        clock: Clock | None = None,
        revocation_ledger: Any = None,
        status_list_service: Any = None,
    ) -> None:
        self._ledger = revocation_ledger
        # Lists are published on first read. Without this service a list nobody
        # has fetched yet would make every credential on it look unverifiable.
        self._status_list_service = status_list_service
        self._wallets = wallets
        self._credentials = credentials
        self._status_lists = status_lists
        self._proofs = proof_service
        self._audits = audits
        self._backups = backups
        self._restore_jobs = restore_jobs
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_backup(
        self, wallet_id: str, *, owner_user_id: str
    ) -> tuple[WalletBackupRecord, str]:
        wallet = self._wallet(wallet_id, owner_user_id)
        stored = [
            record
            for record in self._credentials.list_by_wallet(
                wallet_id, owner_user_id=owner_user_id, limit=MAX_BACKUP_ITEMS + 1
            )
            if record.raw_credential is not None and record.deleted_at is None
        ]
        if len(stored) > MAX_BACKUP_ITEMS:
            raise WalletBackupTooLargeError(
                f"A wallet backup holds at most {MAX_BACKUP_ITEMS} credentials."
            )
        now = self._now()
        backup_id = f"wbk_{token_urlsafe(18)}"
        payload = _canonical(
            {
                "format": BACKUP_FORMAT,
                "formatVersion": BACKUP_FORMAT_VERSION,
                "backupId": backup_id,
                "walletId": wallet.wallet_id,
                "holderDid": wallet.holder_did,
                "createdAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "items": [
                    {"credentialId": record.credential_id, "credential": dict(record.raw_credential)}
                    for record in sorted(stored, key=lambda item: item.credential_id)
                ],
            }
        )
        if len(payload) > MAX_PAYLOAD_CHARACTERS:
            raise WalletBackupTooLargeError("The wallet backup exceeds the size limit.")
        record = WalletBackupRecord(
            backup_id=backup_id,
            wallet_id=wallet.wallet_id,
            owner_user_id=owner_user_id,
            holder_did=wallet.holder_did,
            format_version=BACKUP_FORMAT_VERSION,
            item_count=len(stored),
            content_digest=_sha256(payload),
            created_at=now,
        )
        try:
            self._backups.insert_one(record.to_document())
        except PyMongoError as error:
            raise PersistenceUnavailableError("Wallet backup metadata is unavailable.") from error
        self._audit(
            AuditEventType.WALLET_BACKUP_CREATED,
            wallet=wallet,
            backup_id=backup_id,
            metadata={"itemCount": str(record.item_count)},
        )
        return record, payload

    def list_backups(
        self, wallet_id: str, *, owner_user_id: str, limit: int = 50
    ) -> tuple[WalletBackupRecord, ...]:
        self._wallet(wallet_id, owner_user_id)
        try:
            documents = list(
                self._backups.find({"walletId": wallet_id, "ownerUserId": owner_user_id})
                .sort("createdAt", -1)
                .limit(limit)
            )
        except PyMongoError as error:
            raise PersistenceUnavailableError("Wallet backup metadata is unavailable.") from error
        return tuple(WalletBackupRecord.from_document(item) for item in documents)

    def preview(
        self, wallet_id: str, backup_id: str, *, owner_user_id: str, payload: str
    ) -> RestorePlan:
        wallet = self._wallet(wallet_id, owner_user_id)
        plan = self._plan(wallet, backup_id, owner_user_id=owner_user_id, payload=payload)
        self._audit(
            AuditEventType.WALLET_RESTORE_PREVIEWED,
            wallet=wallet,
            backup_id=backup_id,
            metadata={"restorable": str(plan.count(RESTORABLE))},
        )
        return plan

    def restore(
        self,
        wallet_id: str,
        backup_id: str,
        *,
        owner_user_id: str,
        payload: str,
        idempotency_key: str,
    ) -> tuple[RestoreJob, bool]:
        """Returns (job, created). A replayed idempotency key returns the first job."""
        wallet = self._wallet(wallet_id, owner_user_id)
        key_hash = _sha256(f"{wallet_id}:{idempotency_key}")
        previous = self._find_job(wallet_id, key_hash)
        if previous is not None:
            if previous.backup_id != backup_id or previous.owner_user_id != owner_user_id:
                raise WalletBackupConflictError(
                    "The idempotency key was already used for another restore."
                )
            return previous, False
        try:
            plan = self._plan(wallet, backup_id, owner_user_id=owner_user_id, payload=payload)
        except WalletBackupError as error:
            self._audit(
                AuditEventType.WALLET_RESTORE_REJECTED,
                wallet=wallet,
                backup_id=backup_id,
                metadata={"code": error.code},
            )
            raise
        items = {item["credentialId"]: item["credential"] for item in json.loads(payload)["items"]}
        restored = 0
        failure_code: str | None = None
        outcomes: list[RestoreItemPlan] = []
        for item in plan.items:
            if item.outcome != RESTORABLE:
                outcomes.append(item)
                continue
            if failure_code is not None:
                outcomes.append(replace(item, outcome=NOT_ATTEMPTED))
                continue
            try:
                self._credentials.add(
                    _persisted(items[item.credential_id], wallet, owner_user_id, self._now())
                )
                restored += 1
                outcomes.append(replace(item, outcome=RESTORED))
            except Exception:  # persistence failure: stop, report as partial, never as success
                failure_code = "PERSISTENCE_FAILED"
                outcomes.append(replace(item, outcome=NOT_ATTEMPTED))
        pending = sum(item.outcome == RESTORABLE for item in plan.items)
        rejected = len(plan.items) - pending - plan.count(ALREADY_PRESENT)
        if failure_code is not None:
            status = "FAILED" if restored == 0 else "PARTIAL"
        elif rejected:
            status = "PARTIAL"
        else:
            status = "COMPLETED"
        job = RestoreJob(
            restore_id=f"wrs_{token_urlsafe(18)}",
            backup_id=backup_id,
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            status=status,
            restored=restored,
            already_present=plan.count(ALREADY_PRESENT),
            rejected=rejected,
            failure_code=failure_code,
            items=tuple(outcomes),
            created_at=self._now(),
        )
        try:
            self._restore_jobs.insert_one(job.to_document(key_hash))
        except DuplicateKeyError:
            # A concurrent request with the same key won; report its job.
            winner = self._find_job(wallet_id, key_hash)
            if winner is None:
                raise WalletBackupConflictError("Concurrent restore did not converge.")
            return winner, False
        except PyMongoError as error:
            raise PersistenceUnavailableError("Wallet restore job could not be recorded.") from error
        self._audit(
            AuditEventType.WALLET_RESTORE_COMPLETED,
            wallet=wallet,
            backup_id=backup_id,
            metadata={
                "restoreId": job.restore_id,
                "status": status,
                "restored": str(restored),
                "rejected": str(rejected),
            },
        )
        return job, True

    def get_restore_job(
        self, wallet_id: str, restore_id: str, *, owner_user_id: str
    ) -> RestoreJob:
        self._wallet(wallet_id, owner_user_id)
        try:
            document = self._restore_jobs.find_one(
                {"restoreId": restore_id, "walletId": wallet_id, "ownerUserId": owner_user_id}
            )
        except PyMongoError as error:
            raise PersistenceUnavailableError("Wallet restore job is unavailable.") from error
        if document is None:
            raise WalletBackupNotFoundError("Restore job was not found.")
        return RestoreJob.from_document(document)

    def _plan(
        self,
        wallet: HolderWallet,
        backup_id: str,
        *,
        owner_user_id: str,
        payload: str,
    ) -> RestorePlan:
        try:
            document = self._backups.find_one({"backupId": backup_id})
        except PyMongoError as error:
            raise PersistenceUnavailableError("Wallet backup metadata is unavailable.") from error
        if document is not None and (
            document.get("walletId") != wallet.wallet_id
            or document.get("ownerUserId") != owner_user_id
        ):
            # A foreign-owner and an other-wallet archive look identical.
            raise WalletBackupNotFoundError("The backup does not belong to this wallet.")
        if len(payload) > MAX_PAYLOAD_CHARACTERS:
            raise WalletBackupTooLargeError("The wallet backup exceeds the size limit.")
        if document is not None and _sha256(payload) != document["contentDigest"]:
            raise WalletBackupIntegrityError(
                "The backup content does not match the integrity record."
            )
        try:
            content = json.loads(payload)
        except ValueError as error:
            raise WalletBackupIntegrityError("The backup content is not valid.") from error
        if (
            not isinstance(content, dict)
            or content.get("format") != BACKUP_FORMAT
            or content.get("formatVersion") != BACKUP_FORMAT_VERSION
            or content.get("backupId") != backup_id
            or not isinstance(content.get("items"), list)
            or len(content["items"]) > MAX_BACKUP_ITEMS
        ):
            raise WalletBackupIntegrityError("The backup header is not supported.")
        if document is not None and content.get("walletId") != wallet.wallet_id:
            raise WalletBackupIntegrityError("The backup header is not supported.")
        # No server row (lost, or a new database): the file stands alone. That is
        # safe because nothing here trusts it: each credential is re-verified
        # against its issuer and must be bound to this wallet's DID.
        backup = (
            WalletBackupRecord.from_document(document)
            if document is not None
            else WalletBackupRecord(
                backup_id=backup_id,
                wallet_id=wallet.wallet_id,
                owner_user_id=owner_user_id,
                holder_did=wallet.holder_did,
                format_version=BACKUP_FORMAT_VERSION,
                item_count=len(content["items"]),
                content_digest=_sha256(payload),
                created_at=self._now(),
            )
        )
        items = tuple(
            self._classify(item, wallet) for item in content.get("items") or ()
        )
        return RestorePlan(backup=backup, items=items)

    def _classify(self, item: Any, wallet: HolderWallet) -> RestoreItemPlan:
        if not isinstance(item, Mapping):
            return RestoreItemPlan("unknown", UNSUPPORTED_ITEM, ())
        credential_id = item.get("credentialId")
        credential = item.get("credential")
        if not isinstance(credential_id, str) or not isinstance(credential, Mapping):
            return RestoreItemPlan(str(credential_id or "unknown"), UNSUPPORTED_ITEM, ())
        raw_types = credential.get("type")
        types = tuple(str(value) for value in raw_types) if isinstance(raw_types, list) else ()
        plan = lambda outcome: RestoreItemPlan(credential_id, outcome, types)  # noqa: E731
        if credential.get("id") != credential_id:
            return plan(UNSUPPORTED_ITEM)
        existing = self._credentials.get_by_credential_id(credential_id)
        if existing is not None and existing.deleted_at is None:
            return plan(
                ALREADY_PRESENT if existing.wallet_id == wallet.wallet_id else HELD_BY_ANOTHER_WALLET
            )
        subject = credential.get("credentialSubject")
        if not isinstance(subject, Mapping) or subject.get("id") != wallet.holder_did:
            return plan(HOLDER_BINDING_MISMATCH)
        try:
            verified = self._proofs.verify_credential(credential, verified_at=self._now())
        except Exception:
            return plan(PROOF_INVALID)
        if not getattr(verified, "verified", False):
            return plan(PROOF_INVALID)
        return plan(self._status_outcome(credential_id, credential))

    def _status_outcome(self, credential_id: str, credential: Mapping[str, Any]) -> str:
        """Revoked if the ledger, the audit log OR the published list says so.

        The ledger is checked first because it outlives credential records. Any
        doubt about it gives STATUS_UNVERIFIABLE, never a restorable credential.
        """
        if self._ledger is not None:
            try:
                if self._ledger.is_revoked(credential_id):
                    return REVOKED
            except Exception:
                return STATUS_UNVERIFIABLE
        try:
            history = self._audits.list_by_subject(credential_id, limit=500)
        except Exception:
            return STATUS_UNVERIFIABLE
        if any(event.event_type is AuditEventType.CREDENTIAL_REVOKED for event in history):
            return REVOKED
        if len(history) >= 500:  # truncated history cannot prove the absence of a revocation
            return STATUS_UNVERIFIABLE
        status = credential.get("credentialStatus")
        if not isinstance(status, Mapping):
            return STATUS_UNVERIFIABLE
        try:
            list_url = str(status.get("statusListCredential") or "")
            index = int(status.get("statusListIndex"))
            publication = self._publication(list_url.rstrip("/").split("/")[-1])
            if publication is None:
                return STATUS_UNVERIFIABLE
            revoked = decode_status_list_bit(publication.encoded_list, index)
        except Exception:
            return STATUS_UNVERIFIABLE
        return REVOKED if revoked else RESTORABLE

    def _publication(self, status_list_id: str) -> Any:
        """The current list, built from entries and the ledger when needed.

        The service raises for a list it cannot rebuild, and the caller turns
        that into STATUS_UNVERIFIABLE.
        """
        if self._status_list_service is not None:
            return self._status_list_service.get_publication(status_list_id)
        return self._status_lists.get(status_list_id)

    def _find_job(self, wallet_id: str, key_hash: str) -> RestoreJob | None:
        try:
            document = self._restore_jobs.find_one(
                {"walletId": wallet_id, "idempotencyKeyHash": key_hash}
            )
        except PyMongoError as error:
            raise PersistenceUnavailableError("Wallet restore job is unavailable.") from error
        return None if document is None else RestoreJob.from_document(document)

    def _wallet(self, wallet_id: str, owner_user_id: str) -> HolderWallet:
        return self._wallets.require_owned_active(
            wallet_id, owner_user_id=owner_user_id, correlation_id=f"wallet-backup:{wallet_id}"
        )

    def _audit(
        self,
        event_type: AuditEventType,
        *,
        wallet: HolderWallet,
        backup_id: str,
        metadata: Mapping[str, str],
    ) -> None:
        now = self._now()
        self._audits.append(
            AuditEvent(
                id=new_object_id(),
                event_type=event_type,
                subject_id=wallet.wallet_id,
                actor_id=wallet.holder_did,
                correlation_id=backup_id,
                metadata=dict(metadata),
                created_at=now,
                updated_at=now,
            )
        )

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)


def _persisted(
    credential: Mapping[str, Any], wallet: HolderWallet, owner_user_id: str, now: datetime
) -> PersistedCredential:
    """Rebuild the record exactly as issuance stores it (JCS digest, embedded status entry)."""
    status = credential.get("credentialStatus") or {}
    valid_from = _parse_time(credential.get("validFrom")) or now
    has_status = "statusListIndex" in status
    return PersistedCredential(
        id=new_object_id(),
        credential_id=credential["id"],
        issuer_did=str(credential["issuer"]),
        holder_did=wallet.holder_did,
        credential_type=tuple(str(value) for value in credential["type"]),
        issuance_date=valid_from,
        expiration_date=_parse_time(credential.get("validUntil")),
        credential_hash=_CANONICALIZER.calculate_digest(credential).hex(),
        status=CredentialStatus.ACTIVE,
        raw_credential=dict(credential),
        status_list_id=str(status.get("statusListCredential", "")).rstrip("/").split("/")[-1] or None,
        status_list_index=int(status["statusListIndex"]) if has_status else None,
        # The status entry is embedded in the credential record; the lost entry
        # id is replaced, while list id, index and entry URN stay as issued.
        status_entry_id=new_object_id() if has_status else None,
        wallet_id=wallet.wallet_id,
        owner_user_id=owner_user_id,
        created_at=now,
        updated_at=now,
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
