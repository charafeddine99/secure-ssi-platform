from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

import httpx
import jwt

from app.application.ports.managed_keys import (
    ManagedKeyRecoveryGateway,
    ManagedKeyRecoveryOutcome,
)
from app.core.config import RecoverySettings
from app.domain.recovery import (
    RecoveryConflictError,
    RecoveryNotFoundError,
    RecoveryPersistenceError,
    RecoveryReason,
)


Clock = Callable[[], datetime]


class IdentityManagedKeyRecoveryGateway(ManagedKeyRecoveryGateway):
    def __init__(
        self,
        settings: RecoverySettings,
        *,
        client: httpx.Client | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            base_url=settings.identity_base_url,
            timeout=settings.identity_timeout_seconds,
        )
        self._owns_client = client is None
        self._clock = clock or (lambda: datetime.now(UTC))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def verify_wallet_owner(self, *, wallet_id: str, owner_user_id: str) -> None:
        token = self._assertion(
            scope="wallet:ownership:read",
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            request_id=token_urlsafe(12),
        )
        try:
            response = self._client.get(
                f"/internal/v1/recovery/wallets/{wallet_id}/owners/{owner_user_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as error:
            raise RecoveryPersistenceError("Identity ownership check is unavailable.") from error
        self._require_success(response, ownership=True)

    def rotate_for_recovery(
        self,
        *,
        request_id: str,
        wallet_id: str,
        owner_user_id: str,
        reason: RecoveryReason,
    ) -> ManagedKeyRecoveryOutcome:
        token = self._assertion(
            scope="managed-key:recover",
            wallet_id=wallet_id,
            owner_user_id=owner_user_id,
            request_id=request_id,
        )
        try:
            response = self._client.post(
                "/internal/v1/recovery/key-rotation",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": f"recovery:{request_id}",
                },
                json={
                    "recoveryRequestId": request_id,
                    "walletId": wallet_id,
                    "ownerUserId": owner_user_id,
                    "reason": reason.value,
                },
            )
        except httpx.HTTPError as error:
            raise RecoveryPersistenceError("Identity key recovery is unavailable.") from error
        self._require_success(response, ownership=False)
        try:
            payload = response.json()
            return ManagedKeyRecoveryOutcome(
                predecessor_key_id=payload["predecessorKeyId"],
                successor_key_id=payload["successorKeyId"],
                predecessor_did=payload["predecessorDid"],
                successor_did=payload["successorDid"],
                provider=payload["provider"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RecoveryPersistenceError("Identity recovery response is invalid.") from error

    def _assertion(
        self,
        *,
        scope: str,
        wallet_id: str,
        owner_user_id: str,
        request_id: str,
    ) -> str:
        now = self._clock().astimezone(UTC).replace(microsecond=0)
        return jwt.encode(
            {
                "iss": self._settings.identity_grant_issuer,
                "sub": owner_user_id,
                "aud": self._settings.identity_grant_audience,
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp()),
                "exp": int(
                    (
                        now
                        + timedelta(
                            seconds=self._settings.identity_grant_lifetime_seconds
                        )
                    ).timestamp()
                ),
                "jti": token_urlsafe(18),
                "scope": scope,
                "wallet_id": wallet_id,
                "request_id": request_id,
            },
            self._settings.identity_grant_secret,
            algorithm="HS256",
        )

    @staticmethod
    def _require_success(response: httpx.Response, *, ownership: bool) -> None:
        if response.status_code in {200, 204}:
            return
        if response.status_code in {401, 403, 404}:
            if ownership:
                raise RecoveryNotFoundError("Wallet was not found.")
            raise RecoveryConflictError("Managed-key recovery was rejected.")
        if response.status_code == 409:
            raise RecoveryConflictError("Managed-key recovery has a lifecycle conflict.")
        raise RecoveryPersistenceError("Identity key recovery failed.")

    def __repr__(self) -> str:
        return (
            "IdentityManagedKeyRecoveryGateway("
            f"base_url={self._settings.identity_base_url!r}, grant_secret=<redacted>)"
        )
