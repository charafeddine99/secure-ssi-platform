from datetime import UTC, datetime

import httpx
import jwt

from app.core.config import load_settings
from app.domain.recovery import RecoveryReason
from app.infrastructure.managed_keys.identity_gateway import (
    IdentityManagedKeyRecoveryGateway,
)
from tests.support import OWNER, WALLET_ID


def test_identity_gateway_uses_bounded_context_grants_and_idempotency() -> None:
    settings = load_settings(
        {"RECOVERY_IDENTITY_GRANT_LIFETIME_SECONDS": "30"}
    )
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.headers["Authorization"].removeprefix("Bearer ")
        claims = jwt.decode(
            token,
            settings.identity_grant_secret,
            algorithms=["HS256"],
            audience=settings.identity_grant_audience,
            issuer=settings.identity_grant_issuer,
        )
        observed.append(claims)
        assert claims["sub"] == OWNER
        assert claims["wallet_id"] == WALLET_ID
        assert claims["exp"] - claims["iat"] == 30
        if request.method == "GET":
            assert claims["scope"] == "wallet:ownership:read"
            return httpx.Response(204)
        assert claims["scope"] == "managed-key:recover"
        assert request.headers["Idempotency-Key"] == (
            "recovery:recovery_0000000000000001"
        )
        return httpx.Response(
            200,
            json={
                "predecessorKeyId": "key_predecessor",
                "successorKeyId": "key_successor",
                "predecessorDid": "did:key:zPredecessor",
                "successorDid": "did:key:zSuccessor",
                "provider": "development",
            },
        )

    client = httpx.Client(
        base_url=settings.identity_base_url,
        transport=httpx.MockTransport(handler),
    )
    gateway = IdentityManagedKeyRecoveryGateway(
        settings,
        client=client,
        clock=lambda: datetime.now(UTC).replace(microsecond=0),
    )

    gateway.verify_wallet_owner(wallet_id=WALLET_ID, owner_user_id=OWNER)
    outcome = gateway.rotate_for_recovery(
        request_id="recovery_0000000000000001",
        wallet_id=WALLET_ID,
        owner_user_id=OWNER,
        reason=RecoveryReason.KEY_LOSS,
    )

    assert len(observed) == 2
    assert outcome.successor_key_id == "key_successor"
    assert settings.identity_grant_secret not in repr(gateway)
    client.close()
