import httpx

from app.core.config import RecoverySettings
from app.core.environment_policy import is_production_like
from app.infrastructure.risk.security_event_forwarder import wallet_subject


class RecoveryRiskUnavailableError(RuntimeError):
    """No trustworthy risk result exists; callers must hold, never pass."""


_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class FraudRecoveryRiskGateway:
    """Sends a hashed subject and the action only. No DID, wallet or name."""

    def __init__(
        self,
        settings: RecoverySettings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._token = settings.fraud_service_token
        self._production = is_production_like(settings.environment)
        self._client = client or httpx.Client(
            base_url=settings.fraud_base_url,
            timeout=settings.fraud_timeout_seconds,
        )

    def assess_recovery(self, *, wallet_id: str, reason: str) -> str:
        if not self._token:
            raise RecoveryRiskUnavailableError("Risk service is not configured.")
        subject = wallet_subject(wallet_id)
        try:
            response = self._client.post(
                "/api/v1/fraud/evaluate",
                headers={"X-Internal-Service-Token": self._token},
                json={"did": subject, "action": "recovery_request"},
            )
            response.raise_for_status()
            body = response.json()
            level = body["risk_level"]
            # A production check that saw no history must not count as LOW.
            if self._production and body.get("data_quality") != "PLATFORM_HISTORY":
                raise RecoveryRiskUnavailableError("Risk result has no platform history.")
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise RecoveryRiskUnavailableError(
                "Risk result could not be obtained."
            ) from error
        if level not in _LEVELS:
            raise RecoveryRiskUnavailableError("Risk result is invalid.")
        del reason
        return str(level)
