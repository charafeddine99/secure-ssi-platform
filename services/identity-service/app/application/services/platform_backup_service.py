"""Platform Backup & Disaster Recovery across the Identity database, the
Recovery database and the revocation ledger.

Archive: ``MAGIC | u32 header length | header JSON | 12-byte nonce | AES-256-GCM
ciphertext``. The header is authenticated as AAD, so format, backup id, source
and key id cannot be swapped. The plaintext is a zlib-compressed stream of BSON
records (collection index specs, then documents), so BSON types survive.

Safety properties:
* The feature is disabled unless a dedicated 32-byte backup key and a private
  backup directory are configured (fail-closed). The key is not a database
  credential and is never written to an archive, manifest, log or response.
* Artifacts are named only by the server-generated backup id; no caller path is
  ever used, so there is no traversal surface.
* Restore runs only through ``restore_to_target``: the target database name must
  carry the ``restore_drill_`` prefix, differ from the source and be empty.
  Nothing in this module can write to the live database.
* Standalone MongoDB offers no cross-collection snapshot. Collections are
  exported one after another; the manifest says so instead of claiming a
  point-in-time snapshot. A watermark on the revocation ledger makes the export
  fail if a revocation lands during it.
* All components travel in one authenticated archive under one backup id, so
  mismatched component backups cannot be combined.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import struct
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_bytes, token_urlsafe
from typing import Any, Mapping, Protocol

import bson
import bson.errors
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.domain.persistence import AuditEvent, AuditEventType
from app.infrastructure.persistence.indexes import PLATFORM_BACKUPS_COLLECTION
from app.infrastructure.persistence.mappers import new_object_id


MAGIC = b"SSIPBAK1"
ARCHIVE_FORMAT = "secure-ssi-platform-backup"
ARCHIVE_FORMAT_VERSION = 2
# Bump when a stored document shape changes incompatibly; restore refuses mismatches.
PLATFORM_SCHEMA_VERSION = 2
CONSISTENCY_MODE = "SEQUENTIAL_EXPORT_WITH_LEDGER_WATERMARK"
IDENTITY_COMPONENT = "identity"
RECOVERY_COMPONENT = "recovery"
LEDGER_COMPONENT = "ledger"
REQUIRED_COMPONENTS = (IDENTITY_COMPONENT, RECOVERY_COMPONENT)
COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"
_LEDGER_COLLECTION = "revocation_ledger_events"
_SESSION_REVOCATIONS_COLLECTION = "session_revocations"
MAX_PLAINTEXT_BYTES = 512 * 1024 * 1024
MAX_HEADER_BYTES = 4096
RESTORE_TARGET_PATTERN = re.compile(r"^restore_drill_[a-z0-9_]{4,40}$")
_BACKUP_ID_PATTERN = re.compile(r"^pbk_[A-Za-z0-9_-]{16,64}$")
# Its own metadata is excluded: a restored drill must not claim the source's jobs.
_EXCLUDED_COLLECTIONS = frozenset({PLATFORM_BACKUPS_COLLECTION})
_INDEX_OPTIONS = (
    "unique",
    "sparse",
    "expireAfterSeconds",
    "partialFilterExpression",
    "collation",
    "hidden",
    "weights",
    "default_language",
    "language_override",
)
_COLLECTION_OPTIONS = (
    "validator",
    "validationLevel",
    "validationAction",
    "capped",
    "size",
    "max",
    "collation",
    "timeseries",
    "expireAfterSeconds",
)

Clock = Callable[[], datetime]


class PlatformBackupError(Exception):
    code = "PLATFORM_BACKUP_ERROR"
    status_code = 400


class PlatformBackupDisabledError(PlatformBackupError):
    code = "PLATFORM_BACKUP_DISABLED"
    status_code = 503


class PlatformBackupNotFoundError(PlatformBackupError):
    code = "PLATFORM_BACKUP_NOT_FOUND"
    status_code = 404


class PlatformBackupIntegrityError(PlatformBackupError):
    code = "PLATFORM_BACKUP_INTEGRITY_FAILED"
    status_code = 422


class PlatformBackupStateError(PlatformBackupError):
    code = "PLATFORM_BACKUP_STATE_CONFLICT"
    status_code = 409


class PlatformRestoreTargetError(PlatformBackupError):
    code = "PLATFORM_RESTORE_TARGET_REJECTED"
    status_code = 422


class PlatformBackupConsistencyError(PlatformBackupError):
    code = "PLATFORM_BACKUP_WATERMARK_MOVED"
    status_code = 409


class BackupKeyWrapper(Protocol):
    """Wraps a per-archive data key inside a KMS. The KMS key never leaves it."""

    @property
    def key_reference(self) -> str: ...

    def wrap(self, data_key: bytes) -> str: ...

    def unwrap(self, wrapped: str) -> bytes: ...


class OffsiteBackupStore(Protocol):
    """A separately controlled, retention-locked store. No implementation ships:
    a real one needs a provider, credentials and a delete-denial test."""

    def put(self, backup_id: str, archive: bytes) -> str: ...


@dataclass(frozen=True)
class PlatformBackupSettings:
    enabled: bool
    directory: Path | None
    key: bytes | None
    retention_seconds: int
    disabled_reason: str | None
    interval_seconds: int = 0
    recovery_uri: str | None = field(default=None, repr=False)
    recovery_database: str = "secure_recovery"
    kms_key_reference: str | None = None

    @property
    def key_id(self) -> str:
        if self.kms_key_reference is not None:
            return "kms:" + hashlib.sha256(self.kms_key_reference.encode()).hexdigest()[:16]
        if self.key is None:
            return "none"
        return hashlib.sha256(b"secure-ssi-platform-backup-key-id:" + self.key).hexdigest()[:16]

    def __repr__(self) -> str:
        return (
            f"PlatformBackupSettings(enabled={self.enabled}, directory=<set>, "
            f"key=<redacted>, retention_seconds={self.retention_seconds})"
        )


def load_platform_backup_settings(environ: Mapping[str, str] | None = None) -> PlatformBackupSettings:
    env = os.environ if environ is None else environ
    retention = _int(env.get("IDENTITY_PLATFORM_BACKUP_RETENTION_SECONDS"), 7 * 24 * 3600)
    if env.get("IDENTITY_PLATFORM_BACKUP_ENABLED", "false").strip().lower() != "true":
        return PlatformBackupSettings(False, None, None, retention, "Platform backup is not enabled.")
    directory_value = env.get("IDENTITY_PLATFORM_BACKUP_DIR", "").strip()
    if not directory_value or not os.path.isabs(directory_value):
        return PlatformBackupSettings(False, None, None, retention, "Backup directory is not configured.")
    kms_reference = env.get("IDENTITY_PLATFORM_BACKUP_KMS_KEY_REFERENCE", "").strip() or None
    try:
        key = base64.b64decode(env.get("IDENTITY_PLATFORM_BACKUP_KEY_BASE64", ""), validate=True)
    except (binascii.Error, ValueError):
        key = b""
    if kms_reference is None and len(key) != 32:
        return PlatformBackupSettings(
            False, None, None, retention, "Backup encryption key must be 32 random bytes (base64)."
        )
    if not 60 <= retention <= 400 * 24 * 3600:
        return PlatformBackupSettings(False, None, None, retention, "Backup retention is out of bounds.")
    return PlatformBackupSettings(
        True,
        Path(directory_value),
        key or None,
        retention,
        None,
        interval_seconds=_int(env.get("IDENTITY_PLATFORM_BACKUP_INTERVAL_SECONDS"), 0),
        recovery_uri=env.get("IDENTITY_PLATFORM_BACKUP_RECOVERY_URI", "").strip() or None,
        recovery_database=(
            env.get("IDENTITY_PLATFORM_BACKUP_RECOVERY_DATABASE", "").strip() or "secure_recovery"
        ),
        kms_key_reference=kms_reference,
    )


@dataclass(frozen=True)
class CollectionSummary:
    name: str
    documents: int
    indexes: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        return {"name": self.name, "documents": self.documents, "indexes": list(self.indexes)}

    @classmethod
    def from_document(cls, value: Mapping[str, Any]) -> "CollectionSummary":
        return cls(value["name"], int(value["documents"]), tuple(value.get("indexes") or ()))


@dataclass(frozen=True)
class PlatformBackupRecord:
    backup_id: str
    status: str
    source_database: str
    created_by: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: float | None
    size_bytes: int | None
    archive_sha256: str | None
    schema_version: int
    app_version: str
    consistency: str
    key_id: str
    collections: tuple[CollectionSummary, ...]
    expires_at: datetime | None
    failure_code: str | None
    last_verified_at: datetime | None
    last_verify_result: str | None
    completeness: str = PARTIAL
    components: tuple[str, ...] = ()
    watermark: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "_id": self.backup_id,
            "backupId": self.backup_id,
            "status": self.status,
            "sourceDatabase": self.source_database,
            "createdBy": self.created_by,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "durationMs": self.duration_ms,
            "sizeBytes": self.size_bytes,
            "archiveSha256": self.archive_sha256,
            "schemaVersion": self.schema_version,
            "appVersion": self.app_version,
            "consistency": self.consistency,
            "keyId": self.key_id,
            "collections": [item.to_document() for item in self.collections],
            "expiresAt": self.expires_at,
            "failureCode": self.failure_code,
            "lastVerifiedAt": self.last_verified_at,
            "lastVerifyResult": self.last_verify_result,
            "completeness": self.completeness,
            "components": list(self.components),
            "watermark": self.watermark,
            "createdAt": self.started_at,
        }

    @classmethod
    def from_document(cls, value: Mapping[str, Any]) -> "PlatformBackupRecord":
        return cls(
            backup_id=value["backupId"],
            status=value["status"],
            source_database=value["sourceDatabase"],
            created_by=value["createdBy"],
            started_at=_aware(value["startedAt"]),
            finished_at=_aware(value.get("finishedAt")),
            duration_ms=value.get("durationMs"),
            size_bytes=value.get("sizeBytes"),
            archive_sha256=value.get("archiveSha256"),
            schema_version=int(value["schemaVersion"]),
            app_version=value.get("appVersion", "unknown"),
            consistency=value.get("consistency", CONSISTENCY_MODE),
            key_id=value.get("keyId", "none"),
            collections=tuple(CollectionSummary.from_document(item) for item in value.get("collections") or ()),
            expires_at=_aware(value.get("expiresAt")),
            failure_code=value.get("failureCode"),
            last_verified_at=_aware(value.get("lastVerifiedAt")),
            last_verify_result=value.get("lastVerifyResult"),
            completeness=value.get("completeness", PARTIAL),
            components=tuple(value.get("components") or ()),
            watermark=value.get("watermark"),
        )


@dataclass(frozen=True)
class ArchiveContents:
    header: Mapping[str, Any]
    collections: tuple[CollectionSummary, ...]
    index_specs: Mapping[str, tuple[Mapping[str, Any], ...]]
    documents: Mapping[str, tuple[Mapping[str, Any], ...]]
    collection_options: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class RestorePreview:
    backup: PlatformBackupRecord
    target_database: str
    target_name_accepted: bool
    schema_compatible: bool
    integrity_verified: bool
    collections: tuple[CollectionSummary, ...]
    blocking_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RestoreReport:
    backup_id: str
    target_database: str
    status: str
    duration_ms: float
    collections: tuple[dict[str, Any], ...]
    failure_code: str | None


# ---------------------------------------------------------------- archive codec


def encode_archive(
    *, header: Mapping[str, Any], plaintext: bytes, key: bytes, nonce: bytes | None = None
) -> bytes:
    header_bytes = _canonical(header).encode("utf-8")
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise PlatformBackupIntegrityError("Archive header is too large.")
    nonce = nonce or token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, zlib.compress(plaintext, 6), MAGIC + header_bytes)
    return MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes + nonce + ciphertext


def read_header(archive: bytes) -> dict[str, Any]:
    """Unauthenticated view, used only to find the wrapped key for decryption."""
    if len(archive) < len(MAGIC) + 4 or not archive.startswith(MAGIC):
        raise PlatformBackupIntegrityError("Archive is not a platform backup.")
    (length,) = struct.unpack(">I", archive[len(MAGIC) : len(MAGIC) + 4])
    if not 2 <= length <= MAX_HEADER_BYTES:
        raise PlatformBackupIntegrityError("Archive header length is invalid.")
    try:
        value = json.loads(archive[len(MAGIC) + 4 : len(MAGIC) + 4 + length])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlatformBackupIntegrityError("Archive header is malformed.") from error
    if not isinstance(value, dict):
        raise PlatformBackupIntegrityError("Archive header is malformed.")
    return value


def decode_archive(archive: bytes, *, key: bytes, expected_backup_id: str | None = None) -> tuple[dict[str, Any], bytes]:
    """Authenticate and decrypt; any tampering, wrong key or wrong id fails closed."""
    if len(archive) < len(MAGIC) + 4 + 12 + 16 or not archive.startswith(MAGIC):
        raise PlatformBackupIntegrityError("Archive is not a platform backup.")
    (header_length,) = struct.unpack(">I", archive[len(MAGIC) : len(MAGIC) + 4])
    if not 2 <= header_length <= MAX_HEADER_BYTES:
        raise PlatformBackupIntegrityError("Archive header length is invalid.")
    start = len(MAGIC) + 4
    header_bytes = archive[start : start + header_length]
    nonce = archive[start + header_length : start + header_length + 12]
    ciphertext = archive[start + header_length + 12 :]
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlatformBackupIntegrityError("Archive header is malformed.") from error
    if (
        not isinstance(header, dict)
        or header.get("format") != ARCHIVE_FORMAT
        or header.get("formatVersion") != ARCHIVE_FORMAT_VERSION
        or header.get("cipher") != "AES-256-GCM"
        or header.get("compression") != "zlib"
    ):
        raise PlatformBackupIntegrityError("Archive format or cipher is not supported.")
    if expected_backup_id is not None and header.get("backupId") != expected_backup_id:
        raise PlatformBackupIntegrityError("Archive belongs to another backup.")
    try:
        compressed = AESGCM(key).decrypt(nonce, ciphertext, MAGIC + header_bytes)
    except InvalidTag as error:
        raise PlatformBackupIntegrityError(
            "Archive authentication failed (tampered archive or wrong key)."
        ) from error
    decompressor = zlib.decompressobj()
    plaintext = decompressor.decompress(compressed, MAX_PLAINTEXT_BYTES + 1)
    if len(plaintext) > MAX_PLAINTEXT_BYTES or decompressor.unconsumed_tail:
        raise PlatformBackupIntegrityError("Archive expands beyond the size limit.")
    return header, plaintext


def parse_plaintext(plaintext: bytes) -> ArchiveContents:
    specs: dict[str, list[Mapping[str, Any]]] = {}
    documents: dict[str, list[Mapping[str, Any]]] = {}
    options: dict[str, Mapping[str, Any]] = {}
    header: Mapping[str, Any] = {}
    try:
        for record in bson.decode_iter(plaintext):
            kind = record.get("t")
            if kind == "manifest":
                header = record["m"]
            elif kind == "collection":
                specs[record["c"]] = list(record.get("i") or ())
                options[record["c"]] = record.get("o") or {}
                documents.setdefault(record["c"], [])
            elif kind == "document":
                documents[record["c"]].append(record["d"])
            else:
                raise PlatformBackupIntegrityError("Archive contains an unknown record.")
    except (bson.errors.BSONError, KeyError, TypeError) as error:
        raise PlatformBackupIntegrityError("Archive content is malformed.") from error
    summaries = tuple(
        CollectionSummary(
            name,
            len(documents[name]),
            tuple(sorted(spec["name"] for spec in specs[name])),
        )
        for name in sorted(specs)
    )
    return ArchiveContents(
        header=header,
        collections=summaries,
        index_specs={name: tuple(value) for name, value in specs.items()},
        documents={name: tuple(value) for name, value in documents.items()},
        collection_options=options,
    )


# ---------------------------------------------------------------- service


class PlatformBackupService:
    def __init__(
        self,
        *,
        database: Database[dict[str, Any]],
        settings: PlatformBackupSettings,
        audits: Any,
        app_version: str,
        clock: Clock | None = None,
        additional_sources: Mapping[str, Database[dict[str, Any]]] | None = None,
        key_wrapper: BackupKeyWrapper | None = None,
        offsite: OffsiteBackupStore | None = None,
    ) -> None:
        self._additional = dict(additional_sources or {})
        self._key_wrapper = key_wrapper
        self._offsite = offsite
        self._database = database
        self._settings = settings
        self._audits = audits
        self._app_version = app_version
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def settings(self) -> PlatformBackupSettings:
        return self._settings

    @property
    def _records(self) -> Any:
        return self._database[PLATFORM_BACKUPS_COLLECTION]

    def list_backups(self, *, limit: int = 50) -> tuple[PlatformBackupRecord, ...]:
        try:
            documents = list(self._records.find({}).sort("startedAt", -1).limit(limit))
        except PyMongoError as error:
            raise PlatformBackupDisabledError("Backup metadata is unavailable.") from error
        return tuple(PlatformBackupRecord.from_document(item) for item in documents)

    def get(self, backup_id: str) -> PlatformBackupRecord:
        if not _BACKUP_ID_PATTERN.fullmatch(backup_id):
            raise PlatformBackupNotFoundError("Backup was not found.")
        document = self._records.find_one({"backupId": backup_id})
        if document is None:
            raise PlatformBackupNotFoundError("Backup was not found.")
        return PlatformBackupRecord.from_document(document)

    def create_backup(self, *, actor_id: str) -> PlatformBackupRecord:
        settings = self._require_enabled()
        started = self._now()
        clock_start = time.perf_counter()
        backup_id = f"pbk_{token_urlsafe(18)}"
        record = PlatformBackupRecord(
            backup_id=backup_id,
            status="RUNNING",
            source_database=self._database.name,
            created_by=actor_id,
            started_at=started,
            finished_at=None,
            duration_ms=None,
            size_bytes=None,
            archive_sha256=None,
            schema_version=PLATFORM_SCHEMA_VERSION,
            app_version=self._app_version,
            consistency=CONSISTENCY_MODE,
            key_id=settings.key_id,
            collections=(),
            expires_at=None,
            failure_code=None,
            last_verified_at=None,
            last_verify_result=None,
            components=self._component_names(),
            completeness=self._completeness(),
        )
        self._records.insert_one(record.to_document())
        try:
            watermark = self._ledger_watermark()
            plaintext, summaries = self._export()
            if self._ledger_watermark() != watermark:
                raise PlatformBackupConsistencyError(
                    "A revocation landed during the export; run the backup again."
                )
            data_key, wrapped = self._new_archive_key(settings)
            header = {
                "format": ARCHIVE_FORMAT,
                "formatVersion": ARCHIVE_FORMAT_VERSION,
                "backupId": backup_id,
                "sourceDatabase": self._database.name,
                "schemaVersion": PLATFORM_SCHEMA_VERSION,
                "createdAt": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "cipher": "AES-256-GCM",
                "compression": "zlib",
                "keyId": settings.key_id,
                "components": list(record.components),
                "completeness": record.completeness,
                "watermark": watermark,
                "wrappedKey": wrapped,
                "mongoUsers": "RECREATE_FROM_INIT_SCRIPT",
            }
            archive = encode_archive(header=header, plaintext=plaintext, key=data_key)
            path = self._artifact_path(backup_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".partial")
            with open(temporary, "xb") as handle:
                handle.write(archive)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        except Exception as error:
            failed = self._finish(record, clock_start, status="FAILED", failure_code=_failure_code(error))
            self._audit(AuditEventType.PLATFORM_BACKUP_FAILED, actor_id, backup_id, {"code": failed.failure_code or ""})
            if isinstance(error, PlatformBackupError):
                raise
            raise PlatformBackupStateError("The platform backup failed.") from error
        finished = self._finish(
            record,
            clock_start,
            status="SUCCEEDED",
            size_bytes=len(archive),
            archive_sha256=hashlib.sha256(archive).hexdigest(),
            collections=summaries,
            expires_at=started + timedelta(seconds=settings.retention_seconds),
            watermark=watermark,
        )
        if self._offsite is not None:
            self._records.update_one(
                {"backupId": backup_id},
                {"$set": {"offsiteReference": self._offsite.put(backup_id, archive)}},
            )
        self._audit(
            AuditEventType.PLATFORM_BACKUP_CREATED,
            actor_id,
            backup_id,
            {"collections": str(len(summaries)), "sizeBytes": str(len(archive))},
        )
        self.expire_due(actor_id=actor_id)
        return finished

    def verify(self, backup_id: str, *, actor_id: str) -> tuple[PlatformBackupRecord, ArchiveContents]:
        settings = self._require_enabled()
        record = self.get(backup_id)
        if record.status != "SUCCEEDED":
            raise PlatformBackupStateError("Only a succeeded, unexpired backup can be verified.")
        now = self._now()
        try:
            contents = self._load(record, settings)
        except PlatformBackupError as error:
            self._records.update_one(
                {"backupId": backup_id},
                {"$set": {"lastVerifiedAt": now, "lastVerifyResult": error.code}},
            )
            self._audit(AuditEventType.PLATFORM_BACKUP_VERIFY_FAILED, actor_id, backup_id, {"code": error.code})
            raise
        self._records.update_one(
            {"backupId": backup_id},
            {"$set": {"lastVerifiedAt": now, "lastVerifyResult": "VERIFIED"}},
        )
        self._audit(AuditEventType.PLATFORM_BACKUP_VERIFIED, actor_id, backup_id, {})
        return self.get(backup_id), contents

    def preview_restore(self, backup_id: str, *, target_database: str, actor_id: str) -> RestorePreview:
        record = self.get(backup_id)
        reasons: list[str] = []
        name_ok = bool(RESTORE_TARGET_PATTERN.fullmatch(target_database)) and (
            target_database != record.source_database and target_database != self._database.name
        )
        if not name_ok:
            reasons.append(
                "Target must be a separate drill database named restore_drill_<suffix>; "
                "the source or live database is never a restore target."
            )
        schema_ok = record.schema_version == PLATFORM_SCHEMA_VERSION
        if not schema_ok:
            reasons.append("Archive schema version differs from this service; a migration is required.")
        integrity_ok = False
        collections = record.collections
        if record.status != "SUCCEEDED":
            reasons.append(f"Backup status is {record.status}.")
        else:
            try:
                _, contents = self.verify(backup_id, actor_id=actor_id)
                integrity_ok = True
                collections = contents.collections
            except PlatformBackupError as error:
                reasons.append(f"Archive verification failed: {error.code}.")
        reasons.append(
            "Execution is CLI-only against empty drill databases and needs a "
            "two-person approval; live cutover is not automated."
        )
        self._audit(
            AuditEventType.PLATFORM_RESTORE_PREVIEWED,
            actor_id,
            backup_id,
            {"targetAccepted": str(name_ok).lower(), "integrity": str(integrity_ok).lower()},
        )
        return RestorePreview(
            backup=record,
            target_database=target_database,
            target_name_accepted=name_ok,
            schema_compatible=schema_ok,
            integrity_verified=integrity_ok,
            collections=collections,
            blocking_reasons=tuple(reasons),
        )

    def expire_due(self, *, actor_id: str) -> int:
        """Retention. Does nothing while storage is off, so metadata can never
        claim an artifact is gone when it was left in place, and always keeps
        the newest complete, verified backup."""
        settings = self._settings
        if not settings.enabled or settings.directory is None:
            return 0
        now = self._now()
        expired = 0
        records = [
            PlatformBackupRecord.from_document(document)
            for document in self._records.find({"status": "SUCCEEDED"})
        ]
        keep = self._last_known_good(records)
        for record in records:
            if record.expires_at is None or record.expires_at > now:
                continue
            if keep is not None and record.backup_id == keep.backup_id:
                continue
            path = self._artifact_path(record.backup_id)
            if path.exists():
                path.unlink()
            self._records.update_one(
                {"backupId": record.backup_id, "status": "SUCCEEDED"},
                {"$set": {"status": "EXPIRED"}},
            )
            self._audit(AuditEventType.PLATFORM_BACKUP_EXPIRED, actor_id, record.backup_id, {})
            expired += 1
        return expired

    @staticmethod
    def _last_known_good(
        records: list[PlatformBackupRecord],
    ) -> PlatformBackupRecord | None:
        verified = [
            item
            for item in records
            if item.completeness == COMPLETE and item.last_verify_result == "VERIFIED"
        ]
        return max(verified, key=lambda item: item.started_at, default=None)

    def last_verified_restore_point(self) -> PlatformBackupRecord | None:
        records = [
            PlatformBackupRecord.from_document(document)
            for document in self._records.find({"status": "SUCCEEDED"})
        ]
        return self._last_known_good(records)

    def recover_interrupted(self, *, stale_after_seconds: int = 3600) -> int:
        """A worker that died mid-backup leaves RUNNING forever without this."""
        cutoff = self._now() - timedelta(seconds=stale_after_seconds)
        recovered = 0
        for document in list(self._records.find({"status": "RUNNING"})):
            record = PlatformBackupRecord.from_document(document)
            if record.started_at > cutoff:
                continue
            result = self._records.update_one(
                {"backupId": record.backup_id, "status": "RUNNING"},
                {"$set": {"status": "FAILED", "failureCode": "INTERRUPTED", "finishedAt": self._now()}},
            )
            recovered += getattr(result, "matched_count", 0)
        return recovered

    def restore_to_target(
        self,
        backup_id: str,
        *,
        target: Database[dict[str, Any]],
        actor_id: str,
        additional_targets: Mapping[str, Database[dict[str, Any]]] | None = None,
    ) -> RestoreReport:
        """Restore into empty, separately named drill databases. CLI use only;
        the CLI consumes a two-person approval before calling this."""
        settings = self._require_enabled()
        record = self.get(backup_id)
        extras = dict(additional_targets or {})
        name = target.name
        targets = {IDENTITY_COMPONENT: target, **extras}
        for component, database in targets.items():
            if (
                not RESTORE_TARGET_PATTERN.fullmatch(database.name)
                or database.name in {record.source_database, self._database.name}
            ):
                raise PlatformRestoreTargetError("Restore target is not a separate drill database.")
            if database.list_collection_names():
                raise PlatformRestoreTargetError("Restore target database is not empty.")
        if len({database.name for database in targets.values()}) != len(targets):
            raise PlatformRestoreTargetError("Each component needs its own drill database.")
        if record.schema_version != PLATFORM_SCHEMA_VERSION:
            raise PlatformRestoreTargetError("Archive schema version is not compatible.")
        if record.completeness != COMPLETE:
            raise PlatformRestoreTargetError("A partial backup cannot become a restore point.")
        missing = set(record.components) - set(targets)
        if missing:
            raise PlatformRestoreTargetError("Every backed-up component needs a restore target.")
        contents = self._load(record, settings)
        started = time.perf_counter()
        try:
            results = []
            for collection in contents.collections:
                component, plain_name = _split_component(collection.name)
                database = targets[component]
                options = contents.collection_options.get(collection.name) or {}
                database.create_collection(plain_name, **dict(options))
                destination = database[plain_name]
                batch = list(contents.documents[collection.name])
                if batch:
                    destination.insert_many(batch, ordered=True)
                for spec in contents.index_specs[collection.name]:
                    if spec["name"] == "_id_":
                        continue
                    index_options = {key: spec[key] for key in _INDEX_OPTIONS if key in spec}
                    destination.create_index(
                        [(item, direction) for item, direction in spec["key"]],
                        name=spec["name"],
                        **index_options,
                    )
            consistent = True
            for collection in contents.collections:
                component, plain_name = _split_component(collection.name)
                database = targets[component]
                restored = database[plain_name].count_documents({})
                index_match = _index_fingerprint(
                    database[plain_name].index_information()
                ) == _spec_fingerprint(contents.index_specs[collection.name])
                options_match = _collection_options(database, plain_name) == dict(
                    contents.collection_options.get(collection.name) or {}
                )
                matches = (
                    restored == collection.documents and index_match and options_match
                )
                consistent = consistent and matches
                results.append(
                    {
                        "name": collection.name,
                        "expectedDocuments": collection.documents,
                        "restoredDocuments": restored,
                        "indexesMatch": index_match,
                        "optionsMatch": options_match,
                    }
                )
            if not consistent:
                raise PlatformBackupIntegrityError("Restored data does not match the archive.")
            if _tip_of(targets.get(LEDGER_COMPONENT, target)) != record.watermark:
                raise PlatformBackupIntegrityError("Restored ledger does not match the watermark.")
            # Nothing issued before this moment is trusted, even if an old
            # session or denylist snapshot came back with the data.
            target[_SESSION_REVOCATIONS_COLLECTION].replace_one(
                {"_id": "global"},
                {"_id": "global", "kind": "global", "reason": "platform_restore", "notBefore": self._now()},
                upsert=True,
            )
        except Exception as error:
            # Targets were verified empty and drill-named, so this cannot touch live data.
            status = "FAILED_ROLLED_BACK"
            for database in targets.values():
                try:
                    if database.list_collection_names():
                        database.client.drop_database(database.name)
                except Exception:
                    status = "FAILED_ROLLBACK_INCOMPLETE"
            return RestoreReport(
                backup_id, name, status,
                (time.perf_counter() - started) * 1000, (), _failure_code(error),
            )
        return RestoreReport(
            backup_id, name, "RESTORED_AND_VERIFIED",
            (time.perf_counter() - started) * 1000, tuple(results), None,
        )

    # ------------------------------------------------------------ internals

    @property
    def component_names(self) -> tuple[str, ...]:
        return self._component_names()

    def _component_names(self) -> tuple[str, ...]:
        return (IDENTITY_COMPONENT, *sorted(self._additional))

    def _completeness(self) -> str:
        return (
            COMPLETE
            if set(REQUIRED_COMPONENTS) <= set(self._component_names())
            else PARTIAL
        )

    def _ledger_watermark(self) -> str:
        return _tip_of(self._additional.get(LEDGER_COMPONENT, self._database))

    def _new_archive_key(self, settings: PlatformBackupSettings) -> tuple[bytes, str | None]:
        if self._key_wrapper is None:
            if settings.key is None:
                raise PlatformBackupDisabledError("No backup key is available.")
            return settings.key, None
        data_key = token_bytes(32)
        return data_key, self._key_wrapper.wrap(data_key)

    def _archive_key(self, archive: bytes, settings: PlatformBackupSettings) -> bytes:
        wrapped = read_header(archive).get("wrappedKey")
        if wrapped is None:
            if settings.key is None:
                raise PlatformBackupIntegrityError("No key can open this archive.")
            return settings.key
        if self._key_wrapper is None:
            raise PlatformBackupIntegrityError("No KMS is configured to open this archive.")
        try:
            return self._key_wrapper.unwrap(str(wrapped))
        except Exception as error:
            raise PlatformBackupIntegrityError("The archive key could not be unwrapped.") from error

    def _export(self) -> tuple[bytes, tuple[CollectionSummary, ...]]:
        chunks: list[bytes] = []
        summaries: list[CollectionSummary] = []
        size = 0
        sources = {IDENTITY_COMPONENT: self._database, **self._additional}
        for component, database in sources.items():
            for name in sorted(database.list_collection_names()):
                if name in _EXCLUDED_COLLECTIONS or name.startswith("system."):
                    continue
                archive_name = name if component == IDENTITY_COMPONENT else f"{component}/{name}"
                collection = database[name]
                specs = []
                for index_name, info in collection.index_information().items():
                    spec = {"name": index_name, "key": [list(pair) for pair in info["key"]]}
                    spec.update({key: info[key] for key in _INDEX_OPTIONS if key in info})
                    specs.append(spec)
                chunks.append(
                    bson.encode(
                        {
                            "t": "collection",
                            "c": archive_name,
                            "i": specs,
                            "o": _collection_options(database, name),
                        }
                    )
                )
                count = 0
                for document in collection.find({}).sort("_id", 1):
                    encoded = bson.encode({"t": "document", "c": archive_name, "d": document})
                    size += len(encoded)
                    if size > MAX_PLAINTEXT_BYTES:
                        raise PlatformBackupStateError("Database exceeds the backup size limit.")
                    chunks.append(encoded)
                    count += 1
                summaries.append(
                    CollectionSummary(archive_name, count, tuple(sorted(spec["name"] for spec in specs)))
                )
        ordered = tuple(sorted(summaries, key=lambda item: item.name))
        return b"".join(chunks), ordered

    def _load(self, record: PlatformBackupRecord, settings: PlatformBackupSettings) -> ArchiveContents:
        path = self._artifact_path(record.backup_id)
        if not path.is_file():
            raise PlatformBackupIntegrityError("Backup artifact is missing.")
        archive = path.read_bytes()
        if record.archive_sha256 != hashlib.sha256(archive).hexdigest():
            raise PlatformBackupIntegrityError("Backup artifact checksum does not match the manifest.")
        header, plaintext = decode_archive(
            archive,
            key=self._archive_key(archive, settings),
            expected_backup_id=record.backup_id,
        )
        if header.get("keyId") != settings.key_id:
            raise PlatformBackupIntegrityError("Backup was encrypted with another key.")
        contents = parse_plaintext(plaintext)
        if contents.collections != record.collections:
            raise PlatformBackupIntegrityError("Archive collections do not match the manifest.")
        return contents

    def _artifact_path(self, backup_id: str) -> Path:
        if self._settings.directory is None or not _BACKUP_ID_PATTERN.fullmatch(backup_id):
            raise PlatformBackupDisabledError("Backup storage is not configured.")
        return self._settings.directory / f"{backup_id}.ssipbak"

    def _require_enabled(self) -> PlatformBackupSettings:
        if not self._settings.enabled:
            raise PlatformBackupDisabledError(self._settings.disabled_reason or "Platform backup is disabled.")
        return self._settings

    def _finish(self, record: PlatformBackupRecord, clock_start: float, **changes: Any) -> PlatformBackupRecord:
        finished_at = self._now()
        values = {
            "status": changes["status"],
            "finishedAt": finished_at,
            "durationMs": round((time.perf_counter() - clock_start) * 1000, 2),
            "sizeBytes": changes.get("size_bytes"),
            "archiveSha256": changes.get("archive_sha256"),
            "collections": [item.to_document() for item in changes.get("collections", ())],
            "expiresAt": changes.get("expires_at"),
            "failureCode": changes.get("failure_code"),
            "watermark": changes.get("watermark"),
        }
        self._records.update_one({"backupId": record.backup_id}, {"$set": values})
        return self.get(record.backup_id)

    def _audit(self, event_type: AuditEventType, actor_id: str, backup_id: str, metadata: Mapping[str, str]) -> None:
        now = self._now()
        try:
            self._audits.append(
                AuditEvent(
                    id=new_object_id(),
                    event_type=event_type,
                    subject_id=backup_id,
                    actor_id=actor_id,
                    correlation_id=backup_id,
                    metadata={key: value for key, value in metadata.items() if value},
                    created_at=now,
                    updated_at=now,
                )
            )
        except Exception:
            pass  # Audit must not mask the backup outcome; the manifest still records it.

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)


def _split_component(archive_name: str) -> tuple[str, str]:
    component, separator, name = archive_name.partition("/")
    return (component, name) if separator else (IDENTITY_COMPONENT, archive_name)


def _tip_of(database: Any) -> str:
    """The ledger's newest event, or an explicit marker for an empty ledger."""
    documents = list(
        database[_LEDGER_COLLECTION].find({}).sort("sequence", -1).limit(1)
    )
    if not documents:
        return "0:empty"
    return f"{documents[0]['sequence']}:{documents[0]['eventHash']}"


def _collection_options(database: Any, name: str) -> dict[str, Any]:
    for item in database.list_collections(filter={"name": name}):
        options = item.get("options") or {}
        return {key: options[key] for key in _COLLECTION_OPTIONS if key in options}
    return {}


def _spec_fingerprint(specs: Any) -> list[str]:
    return sorted(
        _canonical(
            {
                "name": spec["name"],
                "key": [list(pair) for pair in spec["key"]],
                **{key: spec[key] for key in _INDEX_OPTIONS if key in spec},
            }
        )
        for spec in specs
    )


def _index_fingerprint(information: Mapping[str, Any]) -> list[str]:
    return _spec_fingerprint(
        {
            "name": name,
            "key": info["key"],
            **{key: info[key] for key in _INDEX_OPTIONS if key in info},
        }
        for name, info in information.items()
    )


def _failure_code(error: BaseException) -> str:
    return getattr(error, "code", None) or type(error).__name__.upper()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except ValueError:
        return default


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
