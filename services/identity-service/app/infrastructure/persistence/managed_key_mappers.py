import re
from collections.abc import Mapping
from typing import Any

from app.domain.managed_key import (
    KeyAlgorithm,
    KeyPurpose,
    ManagedKey,
    ManagedKeyState,
)
from app.domain.persistence import DocumentMappingError
from app.infrastructure.persistence.mappers import (
    _datetime,
    _integer,
    _object_id_string,
    _optional_datetime,
    _optional_string,
    _string,
    to_object_id,
)


_FORBIDDEN_FIELD_PARTS = frozenset(
    {
        "authorization",
        "credential",
        "private",
        "seed",
        "mnemonic",
        "secret",
        "token",
    }
)
_FORBIDDEN_EXACT_FIELDS = frozenset(
    {
        "d",
        "keymaterial",
        "keyblob",
        "pem",
        "privatejwk",
        "providercredentials",
    }
)


class ManagedKeyDocumentMapper:
    @staticmethod
    def to_document(key: ManagedKey) -> dict[str, Any]:
        document = {
            "_id": to_object_id(key.id),
            "keyId": key.key_id,
            "walletId": key.wallet_id,
            "ownerUserId": key.owner_user_id,
            "holderDid": key.holder_did,
            "provider": key.provider,
            "providerKeyReference": key.provider_key_reference,
            "algorithm": key.algorithm.value,
            "purpose": key.purpose.value,
            "keyVersion": key.key_version,
            "state": key.state.value,
            "publicKeyMultibase": key.public_key_multibase,
            "fingerprint": key.fingerprint,
            "verificationMethod": key.verification_method,
            "createdAt": key.created_at,
            "updatedAt": key.updated_at,
            "activatedAt": key.activated_at,
            "rotatedAt": key.rotated_at,
            "suspendedAt": key.suspended_at,
            "revokedAt": key.revoked_at,
            "destroyedAt": key.destroyed_at,
            "destructionScheduledAt": key.destruction_scheduled_at,
            "expiresAt": key.expires_at,
            "predecessorKeyId": key.predecessor_key_id,
            "successorKeyId": key.successor_key_id,
            "compromiseReason": key.compromise_reason,
            "idempotencyKeyHash": key.idempotency_key_hash,
            "reconciliationAttempts": key.reconciliation_attempts,
            "reconciliationLeaseUntil": key.reconciliation_lease_until,
            "lastProviderSyncAt": key.last_provider_sync_at,
            "failureCode": key.failure_code,
            "version": key.version,
        }
        reject_private_key_fields(document)
        return document

    @staticmethod
    def from_document(document: dict[str, Any]) -> ManagedKey:
        reject_private_key_fields(document)
        try:
            return ManagedKey(
                id=_object_id_string(document["_id"]),
                key_id=_string(document["keyId"]),
                wallet_id=_string(document["walletId"]),
                owner_user_id=_string(document["ownerUserId"]),
                holder_did=_string(document["holderDid"]),
                provider=_string(document["provider"]),
                provider_key_reference=_optional_string(
                    document.get("providerKeyReference")
                ),
                algorithm=KeyAlgorithm(document["algorithm"]),
                purpose=KeyPurpose(document["purpose"]),
                key_version=_integer(document["keyVersion"]),
                state=ManagedKeyState(document["state"]),
                public_key_multibase=_optional_string(
                    document.get("publicKeyMultibase")
                ),
                fingerprint=_optional_string(document.get("fingerprint")),
                verification_method=_optional_string(
                    document.get("verificationMethod")
                ),
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                activated_at=_optional_datetime(
                    document.get("activatedAt")
                ),
                rotated_at=_optional_datetime(document.get("rotatedAt")),
                suspended_at=_optional_datetime(
                    document.get("suspendedAt")
                ),
                revoked_at=_optional_datetime(document.get("revokedAt")),
                destroyed_at=_optional_datetime(
                    document.get("destroyedAt")
                ),
                destruction_scheduled_at=_optional_datetime(
                    document.get("destructionScheduledAt")
                ),
                expires_at=_optional_datetime(document.get("expiresAt")),
                predecessor_key_id=_optional_string(
                    document.get("predecessorKeyId")
                ),
                successor_key_id=_optional_string(
                    document.get("successorKeyId")
                ),
                compromise_reason=_optional_string(
                    document.get("compromiseReason")
                ),
                idempotency_key_hash=_optional_string(
                    document.get("idempotencyKeyHash")
                ),
                reconciliation_attempts=_integer(
                    document.get("reconciliationAttempts", 0)
                ),
                reconciliation_lease_until=_optional_datetime(
                    document.get("reconciliationLeaseUntil")
                ),
                last_provider_sync_at=_optional_datetime(
                    document.get("lastProviderSyncAt")
                ),
                failure_code=_optional_string(
                    document.get("failureCode")
                ),
                version=_integer(document["version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored managed key document is invalid."
            ) from error


def reject_private_key_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = re.sub(
                r"[^a-z0-9]",
                "",
                str(key).casefold(),
            )
            if normalized in _FORBIDDEN_EXACT_FIELDS or any(
                part in normalized for part in _FORBIDDEN_FIELD_PARTS
            ):
                raise DocumentMappingError(
                    "Private key or provider credential fields are prohibited."
                )
            reject_private_key_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            reject_private_key_fields(child)
