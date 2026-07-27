from typing import Any

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.bitstring_status_list import CredentialStatusEntry
from app.domain.issuance import (
    CredentialAlreadyIssuedError,
    IssuanceStatusSlotConflictError,
)
from app.domain.persistence import (
    PersistedCredential,
    PersistenceUnavailableError,
)
from app.infrastructure.persistence.mappers import CredentialDocumentMapper


class MongoCredentialIssuanceRepository:
    """Atomically stores the credential and its embedded status assignment."""

    def __init__(
        self,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection

    def issue(
        self,
        credential: PersistedCredential,
        *,
        status_entry: CredentialStatusEntry,
    ) -> PersistedCredential:
        self._validate(credential, status_entry=status_entry)
        if self._find(credential.credential_id) is not None:
            raise CredentialAlreadyIssuedError(
                "Credential has already been issued."
            )
        try:
            self._collection.insert_one(
                CredentialDocumentMapper.to_document(credential)
            )
        except DuplicateKeyError:
            if self._find(credential.credential_id) is not None:
                raise CredentialAlreadyIssuedError(
                    "Credential has already been issued."
                ) from None
            raise IssuanceStatusSlotConflictError(
                "Status-list slot was reserved concurrently."
            ) from None
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                "MongoDB credential issuance could not be completed."
            ) from error
        return credential

    def _find(self, credential_id: str) -> dict[str, Any] | None:
        try:
            return self._collection.find_one(
                {"credentialId": credential_id}
            )
        except PyMongoError as error:
            raise PersistenceUnavailableError(
                "MongoDB issuance lookup could not be completed."
            ) from error

    @staticmethod
    def _validate(
        credential: PersistedCredential,
        *,
        status_entry: CredentialStatusEntry,
    ) -> None:
        raw = credential.raw_credential
        if (
            raw is None
            or not isinstance(raw.get("credentialStatus"), dict)
        ):
            raise ValueError(
                "Issued credential and status assignment are inconsistent."
            )
        expected_status = status_entry.to_credential_status(
            status_list_credential_url=raw["credentialStatus"][
                "statusListCredential"
            ]
        )
        if (
            credential.version != 1
            or credential.deleted_at is not None
            or credential.credential_id != status_entry.credential_id
            or credential.issuer_did != status_entry.issuer_did
            or credential.status_list_id != status_entry.status_list_id
            or credential.status_list_index != status_entry.status_list_index
            or credential.status_entry_id != status_entry.id
            or raw.get("credentialStatus") != expected_status
            or "proof" not in raw
        ):
            raise ValueError(
                "Issued credential and status assignment are inconsistent."
            )
