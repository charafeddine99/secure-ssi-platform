from typing import Any

from app.domain.holder_wallet import HolderWallet, WalletStatus
from app.domain.persistence import DocumentMappingError
from app.domain.presentation_challenge import (
    ChallengeStatus,
    PresentationChallenge,
)
from app.infrastructure.persistence.mappers import (
    _datetime,
    _integer,
    _object_id_string,
    _optional_datetime,
    _optional_string,
    _string,
    to_object_id,
)


class HolderWalletDocumentMapper:
    @staticmethod
    def to_document(wallet: HolderWallet) -> dict[str, Any]:
        return {
            "_id": to_object_id(wallet.id),
            "walletId": wallet.wallet_id,
            "ownerUserId": wallet.owner_user_id,
            "holderDid": wallet.holder_did,
            "status": wallet.status.value,
            "keyReference": wallet.key_reference,
            "createdAt": wallet.created_at,
            "updatedAt": wallet.updated_at,
            "version": wallet.version,
            "deletedAt": wallet.deleted_at,
        }

    @staticmethod
    def from_document(document: dict[str, Any]) -> HolderWallet:
        try:
            return HolderWallet(
                id=_object_id_string(document["_id"]),
                wallet_id=_string(document["walletId"]),
                owner_user_id=_string(document["ownerUserId"]),
                holder_did=_string(document["holderDid"]),
                status=WalletStatus(document["status"]),
                key_reference=_string(document["keyReference"]),
                created_at=_datetime(document["createdAt"]),
                updated_at=_datetime(document["updatedAt"]),
                version=_integer(document["version"]),
                deleted_at=_optional_datetime(document.get("deletedAt")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored holder wallet document is invalid."
            ) from error


class PresentationChallengeDocumentMapper:
    @staticmethod
    def to_document(
        challenge: PresentationChallenge,
    ) -> dict[str, Any]:
        return {
            "_id": to_object_id(challenge.id),
            "challengeId": challenge.challenge_id,
            "challenge": challenge.challenge,
            "domain": challenge.domain,
            "audience": challenge.audience,
            "requestedHolderDid": challenge.requested_holder_did,
            "issuedBy": challenge.issued_by,
            "issuedAt": challenge.issued_at,
            "expiresAt": challenge.expires_at,
            "consumedAt": challenge.consumed_at,
            "status": challenge.status.value,
            "version": challenge.version,
        }

    @staticmethod
    def from_document(
        document: dict[str, Any],
    ) -> PresentationChallenge:
        try:
            return PresentationChallenge(
                id=_object_id_string(document["_id"]),
                challenge_id=_string(document["challengeId"]),
                challenge=_string(document["challenge"]),
                domain=_string(document["domain"]),
                audience=_string(document["audience"]),
                requested_holder_did=_optional_string(
                    document.get("requestedHolderDid")
                ),
                issued_by=_string(document["issuedBy"]),
                issued_at=_datetime(document["issuedAt"]),
                expires_at=_datetime(document["expiresAt"]),
                consumed_at=_optional_datetime(
                    document.get("consumedAt")
                ),
                status=ChallengeStatus(document["status"]),
                version=_integer(document["version"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DocumentMappingError(
                "Stored presentation challenge document is invalid."
            ) from error
