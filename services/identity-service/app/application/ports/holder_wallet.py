from datetime import datetime
from typing import Protocol

from app.domain.holder_wallet import HolderWallet, WalletStatus
from app.domain.presentation_challenge import PresentationChallenge


class HolderWalletRepository(Protocol):
    def add(self, wallet: HolderWallet) -> HolderWallet: ...

    def get(self, wallet_id: str) -> HolderWallet | None: ...

    def get_active_by_holder_did(
        self,
        holder_did: str,
    ) -> HolderWallet | None: ...

    def get_by_holder_did(
        self,
        holder_did: str,
    ) -> HolderWallet | None: ...

    def list_by_owner(
        self,
        owner_user_id: str,
        *,
        limit: int = 100,
    ) -> tuple[HolderWallet, ...]: ...

    def update_status(
        self,
        wallet_id: str,
        *,
        status: WalletStatus,
        updated_at: datetime,
        expected_version: int,
    ) -> HolderWallet: ...

    def soft_delete(
        self,
        wallet_id: str,
        *,
        deleted_at: datetime,
        expected_version: int,
    ) -> None: ...


class PresentationChallengeRepository(Protocol):
    def add(
        self,
        challenge: PresentationChallenge,
    ) -> PresentationChallenge: ...

    def get(
        self,
        challenge_id: str,
    ) -> PresentationChallenge | None: ...

    def consume(
        self,
        challenge_id: str,
        *,
        consumed_at: datetime,
        expected_version: int,
        domain: str,
        audience: str,
        requested_holder_did: str | None,
    ) -> PresentationChallenge | None: ...

    def expire(
        self,
        challenge_id: str,
        *,
        expired_at: datetime,
        expected_version: int,
    ) -> PresentationChallenge | None: ...

    def cancel(
        self,
        challenge_id: str,
        *,
        cancelled_at: datetime,
        expected_version: int,
    ) -> PresentationChallenge | None: ...
