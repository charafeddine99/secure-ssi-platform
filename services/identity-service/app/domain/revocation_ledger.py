"""Revocation history that does not depend on credential records surviving.

The chain is tamper-evident inside the trust boundary described in
docs: it is not WORM storage, and nobody should call it immutable.
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.persistence import PersistenceUnavailableError


GENESIS_HASH = "0" * 64
EVENT_REVOKED = "REVOKED"
SOURCE_REVOCATION = "REVOCATION"
SOURCE_BACKFILL = "BACKFILL"


class RevocationLedgerUnavailableError(PersistenceUnavailableError):
    """The ledger cannot be read or written; no clean status may be given."""


class RevocationLedgerIntegrityError(PersistenceUnavailableError):
    """The ledger cannot prove its history; no clean status may be given."""

    def __init__(self, code: str) -> None:
        super().__init__("Revocation history cannot be proven.")
        self.code = code


@dataclass(frozen=True)
class LedgerHead:
    sequence: int
    event_hash: str


@dataclass(frozen=True)
class RevocationEvent:
    event_key: str
    sequence: int
    credential_id: str
    issuer_did: str
    status_list_id: str
    status_list_index: int
    status_purpose: str
    event_type: str
    occurred_at: str
    reason_digest: str
    actor: str
    correlation_id: str
    source: str
    previous_hash: str
    event_hash: str
    mac: str

    def to_document(self) -> dict[str, Any]:
        return {
            "eventKey": self.event_key,
            "sequence": self.sequence,
            "credentialId": self.credential_id,
            "issuerDid": self.issuer_did,
            "statusListId": self.status_list_id,
            "statusListIndex": self.status_list_index,
            "statusPurpose": self.status_purpose,
            "eventType": self.event_type,
            "occurredAt": self.occurred_at,
            "reasonDigest": self.reason_digest,
            "actor": self.actor,
            "correlationId": self.correlation_id,
            "source": self.source,
            "previousHash": self.previous_hash,
            "eventHash": self.event_hash,
            "mac": self.mac,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "RevocationEvent":
        try:
            return cls(
                event_key=str(document["eventKey"]),
                sequence=int(document["sequence"]),
                credential_id=str(document["credentialId"]),
                issuer_did=str(document["issuerDid"]),
                status_list_id=str(document["statusListId"]),
                status_list_index=int(document["statusListIndex"]),
                status_purpose=str(document["statusPurpose"]),
                event_type=str(document["eventType"]),
                occurred_at=str(document["occurredAt"]),
                reason_digest=str(document["reasonDigest"]),
                actor=str(document["actor"]),
                correlation_id=str(document["correlationId"]),
                source=str(document["source"]),
                previous_hash=str(document["previousHash"]),
                event_hash=str(document["eventHash"]),
                mac=str(document["mac"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RevocationLedgerIntegrityError(
                "LEDGER_EVENT_MALFORMED"
            ) from error


def event_key(status_list_id: str, status_list_index: int) -> str:
    """One event per status bit: a replay can only find the same event."""
    return hashlib.sha256(
        f"{status_list_id}\0{status_list_index}\0{EVENT_REVOKED}".encode()
    ).hexdigest()


def compute_event_hash(event: RevocationEvent) -> str:
    fields = event.to_document()
    del fields["eventHash"], fields["mac"]
    canonical = json.dumps(
        fields,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def seal(key: bytes, purpose: str, value: str) -> str:
    return hmac.new(
        key,
        f"{purpose}\0{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def seal_matches(key: bytes, purpose: str, value: str, mac: str) -> bool:
    return hmac.compare_digest(seal(key, purpose, value), mac)
