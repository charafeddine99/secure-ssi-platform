from dataclasses import dataclass

from app.domain.recovery import RecoveryReason


@dataclass(frozen=True)
class ManagedKeyRecoveryOutcome:
    predecessor_key_id: str
    successor_key_id: str
    predecessor_did: str
    successor_did: str
    provider: str


class ManagedKeyRecoveryGateway:
    def verify_wallet_owner(self, *, wallet_id: str, owner_user_id: str) -> None:
        raise NotImplementedError

    def rotate_for_recovery(
        self,
        *,
        request_id: str,
        wallet_id: str,
        owner_user_id: str,
        reason: RecoveryReason,
    ) -> ManagedKeyRecoveryOutcome:
        raise NotImplementedError
