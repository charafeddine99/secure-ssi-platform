"""Sprint 15 — Identity Service Fraud Client.

Connects the OID4VP Verifier to the AI Fraud Detection microservice (Sprint 13-15).
Provides:
1. Dynamic presentation risk evaluation via POST /api/v1/fraud/evaluate
2. Event ingestion reporting via POST /api/v1/fraud/events
3. Explicit risk-unavailable failure; no synthetic LOW fallback
"""

from __future__ import annotations

import logging
import math
import os
import time
from hashlib import sha256
from typing import Any, Dict, Optional

import httpx

from app.config.auth_settings import is_production_like

logger = logging.getLogger(__name__)

FRAUD_SERVICE_URL = os.getenv("FRAUD_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")
FRAUD_INTERNAL_SERVICE_TOKEN = os.getenv("FRAUD_INTERNAL_SERVICE_TOKEN", "")
# Published docker-compose default for local development only.
DEVELOPMENT_ONLY_FRAUD_SERVICE_TOKEN = "local-dev-fraud-service-token-not-for-production"


def _pseudonym(did: str) -> str:
    return "subject:" + sha256(did.encode()).hexdigest()


class FraudRiskUnavailableError(RuntimeError):
    """Risk could not be obtained from the authoritative Fraud Service."""

    code = "RISK_UNAVAILABLE"


class FraudRiskClient:
    """Client for querying Fraud Service evaluation and reporting security events."""

    def __init__(self, base_url: str = FRAUD_SERVICE_URL, timeout_sec: float = 2.0):
        self.base_url = base_url
        self.timeout_sec = timeout_sec

    @staticmethod
    def _internal_headers() -> Dict[str, str]:
        token = os.getenv("FRAUD_INTERNAL_SERVICE_TOKEN", FRAUD_INTERNAL_SERVICE_TOKEN)
        if token == DEVELOPMENT_ONLY_FRAUD_SERVICE_TOKEN and is_production_like(
            os.getenv("IDENTITY_ENVIRONMENT", "development")
        ):
            # Fail closed: risk becomes unavailable instead of trusting a published secret.
            logger.error("The published development fraud service token is refused in production-like mode.")
            return {}
        return {"X-Internal-Service-Token": token} if token else {}

    def evaluate_presentation_risk(
        self,
        *,
        did: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        failed_attempts: int = 0,
        geo_distance_km: float = 0.0,
        time_since_last_action_sec: float = 0.0,
        presentation_frequency_10m: int = 1,
        device_fingerprint: Optional[str] = None,
        device_fingerprint_match: bool = True,
        is_tor_or_proxy: bool = False,
    ) -> Dict[str, Any]:
        """
        Synchronously queries Fraud Service for advisory heuristic risk.
        Returns the score together with its engine version and signal names.
        Risk unavailability is explicit; this client never fabricates a score.
        """
        payload = {
            "did": _pseudonym(did),
            "action": "presentation_verification",
            "failed_attempts": failed_attempts,
            "geo_distance_km": geo_distance_km,
            "time_since_last_action_sec": time_since_last_action_sec,
            "presentation_frequency_10m": presentation_frequency_10m,
            "device_fingerprint_match": device_fingerprint_match,
            "is_tor_or_proxy": is_tor_or_proxy,
        }

        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                res = client.post(
                    f"{self.base_url}/api/v1/fraud/evaluate",
                    json=payload,
                    headers=self._internal_headers(),
                )
                if res.status_code != 200:
                    raise FraudRiskUnavailableError(
                        f"Fraud Service returned HTTP {res.status_code}"
                    )
                data = res.json()
                float_score = float(data["risk_score"])
                if not math.isfinite(float_score) or not 0 <= float_score <= 1:
                    raise ValueError("risk_score is outside the configured [0, 1] range")
                if data.get("advisory_only") is not True:
                    raise ValueError("Fraud Service response is missing advisory_only=true")
                reasons = data.get("reasons")
                risk_signals = data.get("risk_signals")
                if not isinstance(reasons, list) or not all(isinstance(v, str) for v in reasons):
                    raise ValueError("Fraud Service response has invalid reasons")
                if not isinstance(risk_signals, list) or not all(
                    isinstance(v, str) for v in risk_signals
                ):
                    raise ValueError("Fraud Service response has invalid risk_signals")
                model_version = data.get("model_version")
                risk_level = data.get("risk_level")
                if not isinstance(model_version, str) or not model_version.strip():
                    raise ValueError("Fraud Service response has no model version")
                if risk_level not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                    raise ValueError("Fraud Service response has an invalid risk level")
                return {
                    "risk_score": int(round(float_score * 100)),
                    "risk_level": risk_level,
                    "is_anomaly": bool(data.get("is_anomaly", False)),
                    "recommended_action": data.get("recommended_action", "ALLOW"),
                    "reasons": reasons,
                    "model_version": model_version,
                    "risk_signals": risk_signals,
                    "advisory_only": True,
                    "source": "fraud_service",
                }
        except FraudRiskUnavailableError:
            raise
        except Exception as exc:
            logger.warning(
                "Fraud Service evaluation unavailable (%s)", type(exc).__name__
            )
            raise FraudRiskUnavailableError("RISK_UNAVAILABLE") from exc

    def report_event(
        self,
        *,
        event_type: str,
        did: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Asynchronously or best-effort reports security events to Fraud Service feature store."""
        payload = {
            "event_id": f"evt-{int(time.time() * 1000)}",
            "event_type": event_type,
            "did": _pseudonym(did),
            "device_fingerprint": sha256((device_fingerprint or "default-device").encode()).hexdigest(),
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        try:
            with httpx.Client(timeout=1.0) as client:
                client.post(
                    f"{self.base_url}/api/v1/fraud/events",
                    json=payload,
                    headers=self._internal_headers(),
                )
        except Exception:
            pass  # Best effort, never block identity operations on telemetry failure

fraud_client = FraudRiskClient()
