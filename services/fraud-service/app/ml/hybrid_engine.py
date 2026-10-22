"""Deterministic rule-based scoring for the legacy fraud-detection endpoint.

This module contains no trained estimator or learned parameters. Feature names
and thresholds are heuristic signals over synthetic prototype input only.
"""

from typing import Any

import numpy as np


class HybridFraudDetector:
    """Compatibility facade exposing the service's deterministic heuristic."""

    MODEL_VERSION = "rule-heuristic-v1"
    RISK_SIGNALS = [
        "failed_attempt_velocity",
        "unusual_hour",
        "ip_pattern_indicator",
        "device_fingerprint_deviation",
        "burst_rate",
    ]

    def evaluate(self, normalized_features: np.ndarray) -> dict[str, Any]:
        values = np.asarray(normalized_features, dtype=float).reshape(-1)
        if values.size != 6 or not np.isfinite(values).all():
            raise ValueError("Expected six finite normalized heuristic signals.")

        failed, _hour, unusual_hour, ip_pattern, device_deviation, burst = values
        score = (
            0.35 * float(np.clip(failed, 0.0, 1.0))
            + 0.05 * float(np.clip(unusual_hour, 0.0, 1.0))
            + 0.30 * float(np.clip(ip_pattern, 0.0, 1.0))
            + 0.10 * float(np.clip(device_deviation, 0.0, 1.0))
            + 0.30 * float(np.clip(burst, 0.0, 1.0))
        )
        risk_score = int(round(float(np.clip(score, 0.0, 1.0)) * 100))
        reasons = [
            signal
            for signal, value in zip(self.RISK_SIGNALS, (failed, unusual_hour, ip_pattern, device_deviation, burst))
            if float(value) >= 0.65
        ]
        return {
            "risk_score": risk_score,
            "is_fraudulent": risk_score >= 70,
            "anomaly_score": round(float(np.clip(score, 0.0, 1.0)), 4),
            "reasons": reasons or ["No configured heuristic threshold was exceeded."],
            "model_version": self.MODEL_VERSION,
            "advisory_only": True,
            "risk_signals": list(self.RISK_SIGNALS),
        }
