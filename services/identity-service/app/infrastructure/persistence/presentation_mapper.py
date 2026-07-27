from copy import deepcopy
from typing import Any

from app.domain.persistence import DocumentMappingError
from app.domain.presentation import (
    PersistedPresentation,
    PresentationVerificationState,
)
from app.infrastructure.persistence.mappers import (
    _datetime,
    _integer,
    _object_id_string,
    _optional_datetime,
    _optional_integer,
    _optional_string,
    _string,
    to_object_id,
)


class PresentationDocumentMapper:
    @staticmethod
    def to_document(
        presentation: PersistedPresentation,
    ) -> dict[str, Any]:
        return {
            "_id": to_object_id(presentation.id),
            "presentationId": presentation.presentation_id,
            "holderDid": presentation.holder_did,
            "challenge": presentation.challenge,
            "domain": presentation.domain,
            "credentialIds": list(presentation.credential_ids),
            "document": deepcopy(dict(presentation.document)),
            "verificationResult": presentation.verification_result.value,
            "createdAt": presentation.created_at,
            "expiresAt": presentation.expires_at,
            "updatedAt": presentation.updated_at,
            "verifiedAt": presentation.verified_at,
            "rejectionCodes": list(presentation.rejection_codes),
            "walletId": presentation.wallet_id,
            "ownerUserId": presentation.owner_user_id,
            "challengeId": presentation.challenge_id,
            "audience": presentation.audience,
            "processingStartedAt": presentation.processing_started_at,
            "reconciliationAttempts": presentation.reconciliation_attempts,
            "lastReconciledAt": presentation.last_reconciled_at,
            "version": presentation.version,
        }

    @staticmethod
    def from_document(
        document: dict[str, Any],
    ) -> PersistedPresentation:
        try:
            raw_presentation = document["document"]
            if not isinstance(raw_presentation, dict):
                raise TypeError("Expected presentation document.")
            state = PresentationVerificationState(
                document["verificationResult"]
            )
            processing_started_at = _optional_datetime(
                document.get("processingStartedAt")
            )
            if (
                state is PresentationVerificationState.PROCESSING
                and processing_started_at is None
            ):
                processing_started_at = _datetime(document["updatedAt"])
            return PersistedPresentation(
                id=_object_id_string(document["_id"]),
                presentation_id=_string(document["presentationId"]),
                holder_did=_string(document["holderDid"]),
                challenge=_string(document["challenge"]),
                domain=_string(document["domain"]),
                credential_ids=tuple(
                    _string(value) for value in document["credentialIds"]
                ),
                document=deepcopy(raw_presentation),
                verification_result=state,
                created_at=_datetime(document["createdAt"]),
                expires_at=_datetime(document["expiresAt"]),
                updated_at=_datetime(document["updatedAt"]),
                verified_at=_optional_datetime(
                    document.get("verifiedAt")
                ),
                rejection_codes=tuple(
                    _string(value)
                    for value in document.get("rejectionCodes", [])
                ),
                wallet_id=_optional_string(document.get("walletId")),
                owner_user_id=_optional_string(
                    document.get("ownerUserId")
                ),
                challenge_id=_optional_string(
                    document.get("challengeId")
                ),
                audience=_optional_string(document.get("audience")),
                processing_started_at=processing_started_at,
                reconciliation_attempts=(
                    _optional_integer(
                        document.get("reconciliationAttempts")
                    )
                    or 0
                ),
                last_reconciled_at=_optional_datetime(
                    document.get("lastReconciledAt")
                ),
                version=_integer(document["version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored presentation document is invalid."
            ) from error
