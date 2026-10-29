"""Sprint 15 — Identity Service Fraud Client.

Connects the OID4VP Verifier to the AI Fraud Detection microservice (Sprint 13-15).
Provides:
1. Dynamic presentation risk evaluation via POST /api/v1/fraud/evaluate
2. Event ingestion reporting via POST /api/v1/fraud/events
3. Resilient fallback with cryptographic failure protection
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

FRAUD_SERVICE_URL = os.getenv("FRAUD_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")
FRAUD_INTERNAL_SERVICE_TOKEN = os.getenv("FRAUD_INTERNAL_SERVICE_TOKEN", "")
FALLBACK_MODEL_VERSION = "identity-fallback-heuristic-v1"
FALLBACK_RISK_SIGNALS = [
    "failed_attempt_velocity",
    "presentation_frequency",
    "device_fingerprint_mismatch",
    "tor_or_proxy_indicator",
    "geo_distance",
]


class FraudRiskClient:
    """Client for querying Fraud Service evaluation and reporting security events."""

    def __init__(self, base_url: str = FRAUD_SERVICE_URL, timeout_sec: float = 2.0):
        self.base_url = base_url
        self.timeout_sec = timeout_sec

    @staticmethod
    def _internal_headers() -> Dict[str, str]:
        token = os.getenv("FRAUD_INTERNAL_SERVICE_TOKEN", FRAUD_INTERNAL_SERVICE_TOKEN)
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
        Falls back to local heuristic if Fraud Service is unreachable.
        """
        payload = {
            "did": did,
            "action": "presentation_verification",
            "client_ip": client_ip or "127.0.0.1",
            "user_agent": user_agent or "SecureSSI-Verifier/1.0",
            "failed_attempts": failed_attempts,
            "geo_distance_km": geo_distance_km,
            "time_since_last_action_sec": time_since_last_action_sec,
            "presentation_frequency_10m": presentation_frequency_10m,
            "device_fingerprint": device_fingerprint or "default-device",
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
                if res.status_code == 200:
                    data = res.json()
                    float_score = float(data.get("risk_score", 0.15))
                    int_score = int(round(float_score * 100))
                    return {
                        "risk_score": int_score,
                        "risk_level": data.get("risk_level", "LOW"),
                        "is_anomaly": bool(data.get("is_anomaly", False)),
                        "recommended_action": data.get("recommended_action", "ALLOW"),
                        "reasons": data.get("reasons", []),
                        "model_version": data.get("model_version", "unknown"),
                        "risk_signals": data.get("risk_signals", []),
                        "advisory_only": data.get("advisory_only") is True,
                        "source": "fraud_service",
                    }
        except Exception as exc:
            logger.debug("Fraud Service evaluate unreachable (%s), applying heuristic", exc)

        # Fallback heuristic calculation
        return self._heuristic_fallback(
            failed_attempts=failed_attempts,
            is_tor_or_proxy=is_tor_or_proxy,
            device_fingerprint_match=device_fingerprint_match,
            presentation_frequency_10m=presentation_frequency_10m,
            geo_distance_km=geo_distance_km,
        )

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
            "did": did,
            "client_ip": client_ip or "127.0.0.1",
            "user_agent": user_agent or "SecureSSI-Verifier/1.0",
            "device_fingerprint": device_fingerprint or "default-device",
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

    def _heuristic_fallback(
        self,
        *,
        failed_attempts: int,
        is_tor_or_proxy: bool,
        device_fingerprint_match: bool,
        presentation_frequency_10m: int,
        geo_distance_km: float,
    ) -> Dict[str, Any]:
        """Local heuristic if AI Fraud microservice is offline."""
        score = 10
        reasons = []

        if failed_attempts >= 5:
            score += 75
            reasons.append(f"Kritik sayıda başarısız oturum denemesi ({failed_attempts} kez).")
        elif failed_attempts >= 3:
            score += 35
            reasons.append(f"Şüpheli başarısız deneme ({failed_attempts} kez).")

        if is_tor_or_proxy:
            score += 45
            reasons.append("Tor/Anonim proxy çıkış noktası tespit edildi.")

        if not device_fingerprint_match:
            score += 30
            reasons.append("Bilinmeyen cihaz parmak izi.")

        if presentation_frequency_10m > 15:
            score += 50
            reasons.append("Aşırı sunum sıklığı patlaması.")

        if geo_distance_km > 1000.0:
            score += 60
            reasons.append("Olağan dışı coğrafi mesafe sıçraması.")

        score = min(max(score, 0), 100)

        if score >= 85:
            risk_level = "CRITICAL"
            action = "QUARANTINE_ACCOUNT"
        elif score >= 70:
            risk_level = "HIGH"
            action = "MANUAL_REVIEW"
        elif score >= 40:
            risk_level = "MEDIUM"
            action = "REQUIRE_STEP_UP_AUTH"
        else:
            risk_level = "LOW"
            action = "ALLOW"

        return {
            "risk_score": score,
            "risk_level": risk_level,
            "is_anomaly": score >= 40,
            "recommended_action": action,
            "reasons": reasons or ["Tüm parametreler normal profil ile uyumlu."],
            "model_version": FALLBACK_MODEL_VERSION,
            "risk_signals": list(FALLBACK_RISK_SIGNALS),
            "advisory_only": True,
            "source": "identity_fallback_heuristic",
        }


fraud_client = FraudRiskClient()
