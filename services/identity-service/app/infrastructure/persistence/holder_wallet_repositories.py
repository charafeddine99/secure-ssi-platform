from datetime import datetime
from typing import Any

from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.domain.holder_wallet import (
    HolderWallet,
    HolderWalletConflictError,
    WalletStatus,
)
from app.domain.persistence import (
    OptimisticLockError,
    PersistenceUnavailableError,
)
from app.domain.presentation_challenge import (
    ChallengeStatus,
    PresentationChallenge,
    PresentationChallengeConflictError,
)
from app.infrastructure.persistence.holder_wallet_mappers import (
    HolderWalletDocumentMapper,
    PresentationChallengeDocumentMapper,
)


class MongoHolderWalletRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection

    def add(self, wallet: HolderWallet) -> HolderWallet:
        if (
            wallet.version != 1
            or wallet.deleted_at is not None
            or wallet.status is not WalletStatus.ACTIVE
        ):
            raise ValueError("A new wallet must be active at version 1.")
        try:
            self._collection.insert_one(
                HolderWalletDocumentMapper.to_document(wallet)
            )
        except DuplicateKeyError as error:
            raise HolderWalletConflictError(
                "Wallet id, holder DID, or key reference is already in use."
            ) from error
        except PyMongoError as error:
            raise _unavailable("holder wallet insertion") from error
        return wallet

    def get(self, wallet_id: str) -> HolderWallet | None:
        try:
            document = self._collection.find_one(
                {"walletId": wallet_id, "deletedAt": None}
            )
        except PyMongoError as error:
            raise _unavailable("holder wallet lookup") from error
        return (
            None
            if document is None
            else HolderWalletDocumentMapper.from_document(document)
        )

    def get_active_by_holder_did(
        self,
        holder_did: str,
    ) -> HolderWallet | None:
        try:
            document = self._collection.find_one(
                {
                    "holderDid": holder_did,
                    "status": WalletStatus.ACTIVE.value,
                    "deletedAt": None,
                }
            )
        except PyMongoError as error:
            raise _unavailable("holder wallet DID lookup") from error
        return (
            None
            if document is None
            else HolderWalletDocumentMapper.from_document(document)
        )

    def get_by_holder_did(
        self,
        holder_did: str,
    ) -> HolderWallet | None:
        try:
            document = self._collection.find_one(
                {"holderDid": holder_did, "deletedAt": None}
            )
        except PyMongoError as error:
            raise _unavailable("holder wallet DID lookup") from error
        return (
            None
            if document is None
            else HolderWalletDocumentMapper.from_document(document)
        )

    def list_by_owner(
        self,
        owner_user_id: str,
        *,
        limit: int = 100,
    ) -> tuple[HolderWallet, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("Wallet list limit must be between 1 and 500.")
        try:
            return tuple(
                HolderWalletDocumentMapper.from_document(document)
                for document in (
                    self._collection.find(
                        {
                            "ownerUserId": owner_user_id,
                            "deletedAt": None,
                        }
                    )
                    .sort("createdAt", DESCENDING)
                    .limit(limit)
                )
            )
        except PyMongoError as error:
            raise _unavailable("holder wallet listing") from error

    def update_status(
        self,
        wallet_id: str,
        *,
        status: WalletStatus,
        updated_at: datetime,
        expected_version: int,
    ) -> HolderWallet:
        try:
            result = self._collection.update_one(
                {
                    "walletId": wallet_id,
                    "version": expected_version,
                    "deletedAt": None,
                },
                {
                    "$set": {
                        "status": status.value,
                        "updatedAt": updated_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except DuplicateKeyError as error:
            raise HolderWalletConflictError(
                "The holder DID already belongs to an active wallet."
            ) from error
        except PyMongoError as error:
            raise _unavailable("holder wallet status update") from error
        if result.matched_count != 1:
            raise OptimisticLockError(
                "The holder wallet changed or no longer exists."
            )
        updated = self.get(wallet_id)
        if updated is None:
            raise _unavailable("holder wallet status readback")
        return updated

    def soft_delete(
        self,
        wallet_id: str,
        *,
        deleted_at: datetime,
        expected_version: int,
    ) -> None:
        try:
            result = self._collection.update_one(
                {
                    "walletId": wallet_id,
                    "version": expected_version,
                    "deletedAt": None,
                },
                {
                    "$set": {
                        "status": WalletStatus.DISABLED.value,
                        "updatedAt": deleted_at,
                        "deletedAt": deleted_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("holder wallet soft deletion") from error
        if result.matched_count != 1:
            raise OptimisticLockError(
                "The holder wallet changed or no longer exists."
            )

    def update_key_binding(
        self,
        wallet_id: str,
        *,
        holder_did: str,
        key_reference: str,
        updated_at: datetime,
        expected_version: int,
    ) -> HolderWallet:
        try:
            result = self._collection.update_one(
                {
                    "walletId": wallet_id,
                    "version": expected_version,
                    "status": WalletStatus.ACTIVE.value,
                    "deletedAt": None,
                },
                {
                    "$set": {
                        "holderDid": holder_did,
                        "keyReference": key_reference,
                        "updatedAt": updated_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except DuplicateKeyError as error:
            raise HolderWalletConflictError(
                "The holder DID or key reference is already in use."
            ) from error
        except PyMongoError as error:
            raise _unavailable("holder wallet key binding update") from error
        if result.matched_count != 1:
            raise OptimisticLockError(
                "The holder wallet changed or no longer exists."
            )
        updated = self.get(wallet_id)
        if updated is None:
            raise _unavailable("holder wallet key binding readback")
        return updated


class MongoPresentationChallengeRepository:
    def __init__(
        self,
        collection: Collection[dict[str, Any]],
    ) -> None:
        self._collection = collection

    def add(
        self,
        challenge: PresentationChallenge,
    ) -> PresentationChallenge:
        if (
            challenge.version != 1
            or challenge.status is not ChallengeStatus.ISSUED
        ):
            raise ValueError("A new challenge must be issued at version 1.")
        try:
            self._collection.insert_one(
                PresentationChallengeDocumentMapper.to_document(challenge)
            )
        except DuplicateKeyError as error:
            raise PresentationChallengeConflictError(
                "Challenge id or random value is already in use."
            ) from error
        except PyMongoError as error:
            raise _unavailable("presentation challenge insertion") from error
        return challenge

    def get(
        self,
        challenge_id: str,
    ) -> PresentationChallenge | None:
        try:
            document = self._collection.find_one(
                {"challengeId": challenge_id}
            )
        except PyMongoError as error:
            raise _unavailable("presentation challenge lookup") from error
        return (
            None
            if document is None
            else PresentationChallengeDocumentMapper.from_document(document)
        )

    def consume(
        self,
        challenge_id: str,
        *,
        consumed_at: datetime,
        expected_version: int,
        domain: str,
        audience: str,
        requested_holder_did: str | None,
    ) -> PresentationChallenge | None:
        try:
            result = self._collection.update_one(
                {
                    "challengeId": challenge_id,
                    "version": expected_version,
                    "status": ChallengeStatus.ISSUED.value,
                    "expiresAt": {"$gte": consumed_at},
                    "domain": domain,
                    "audience": audience,
                    "requestedHolderDid": requested_holder_did,
                },
                {
                    "$set": {
                        "status": ChallengeStatus.CONSUMED.value,
                        "consumedAt": consumed_at,
                    },
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("presentation challenge consumption") from error
        return None if result.matched_count != 1 else self.get(challenge_id)

    def expire(
        self,
        challenge_id: str,
        *,
        expired_at: datetime,
        expected_version: int,
    ) -> PresentationChallenge | None:
        try:
            result = self._collection.update_one(
                {
                    "challengeId": challenge_id,
                    "version": expected_version,
                    "status": ChallengeStatus.ISSUED.value,
                    "expiresAt": {"$lte": expired_at},
                },
                {
                    "$set": {"status": ChallengeStatus.EXPIRED.value},
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("presentation challenge expiration") from error
        return None if result.matched_count != 1 else self.get(challenge_id)

    def cancel(
        self,
        challenge_id: str,
        *,
        cancelled_at: datetime,
        expected_version: int,
    ) -> PresentationChallenge | None:
        try:
            result = self._collection.update_one(
                {
                    "challengeId": challenge_id,
                    "version": expected_version,
                    "status": ChallengeStatus.ISSUED.value,
                },
                {
                    "$set": {"status": ChallengeStatus.CANCELLED.value},
                    "$inc": {"version": 1},
                },
            )
        except PyMongoError as error:
            raise _unavailable("presentation challenge cancellation") from error
        return None if result.matched_count != 1 else self.get(challenge_id)


def _unavailable(operation: str) -> PersistenceUnavailableError:
    return PersistenceUnavailableError(
        f"MongoDB {operation} could not be completed."
    )
