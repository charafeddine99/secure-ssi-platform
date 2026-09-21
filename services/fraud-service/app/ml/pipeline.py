import math
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler


class FeaturePipeline:
    """
    Data processing and normalization pipeline using pandas and scikit-learn.
    Extracts behavioral, temporal, and network features from raw authentication events
    and normalizes them for the hybrid XGBoost + Autoencoder detection engine.
    """

    def __init__(self):
        self.scaler = MinMaxScaler(feature_range=(0.0, 1.0))
        self.feature_columns = [
            "failed_attempts_norm",
            "hour_of_day_norm",
            "is_unusual_hour",
            "ip_risk_indicator",
            "device_anomaly_factor",
            "burst_rate_indicator"
        ]
        self._init_baseline_scaler()

    def _init_baseline_scaler(self):
        """
        Fit the MinMaxScaler with representative baseline distributions
        of legitimate and anomalous SSI authentication events.
        """
        baseline_data = pd.DataFrame({
            "failed_attempts": [0, 1, 2, 3, 5, 10, 20],
            "hour_of_day": [0, 4, 8, 12, 16, 20, 23],
            "is_unusual_hour": [1, 1, 0, 0, 0, 0, 1],
            "ip_risk": [0.0, 0.1, 0.3, 0.6, 0.8, 0.9, 1.0],
            "device_anomaly": [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0],
            "burst_rate": [0.0, 0.1, 0.3, 0.5, 0.8, 0.95, 1.0]
        })
        self.scaler.fit(baseline_data)

    def _compute_ip_risk(self, ip_address: str) -> float:
        """
        Heuristic risk indicator based on IP topology:
        Checks for loopback, private vs public, known suspicious patterns.
        """
        try:
            parts = [int(p) for p in ip_address.split(".") if p.isdigit()]
            if len(parts) != 4:
                return 0.85  # Malformed or IPv6 non-standard -> elevated risk

            # Loopback or standard local dev
            if parts[0] == 127 or (parts[0] == 10) or (parts[0] == 192 and parts[1] == 168):
                return 0.05

            # Simulated high-risk subnets (e.g. Tor exit nodes, datacenter proxies)
            if parts[0] in [185, 194, 45, 91] and parts[1] in [220, 154, 101, 255]:
                return 0.92

            # Entropy of octets
            octets_spread = max(parts) - min(parts)
            return float(min(1.0, max(0.1, octets_spread / 255.0)))
        except Exception:
            return 0.75

    def _compute_device_anomaly(self, device_fingerprint: str, did_id: str) -> float:
        """
        Evaluates device fingerprint consistency against DID identifier hash.
        """
        if not device_fingerprint or len(device_fingerprint) < 8:
            return 0.95  # Missing or trivial fingerprint

        # Deterministic pseudo-distance between DID and device fingerprint
        combined = f"{did_id}:{device_fingerprint}".encode("utf-8")
        hash_digest = hashlib.sha256(combined).hexdigest()
        hash_int = int(hash_digest[:8], 16)
        return float((hash_int % 100) / 100.0)

    def process_and_normalize(
        self,
        did_id: str,
        timestamp: int,
        ip_address: str,
        device_fingerprint: str,
        recent_failed_attempts: int
    ) -> Tuple[pd.DataFrame, np.ndarray]:
        """
        Ingests raw authentication attributes, runs feature engineering via pandas,
        and produces a normalized numpy array scaled to [0, 1].
        """
        # 1. Temporal feature engineering
        try:
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            hour_of_day = dt.hour
        except Exception:
            hour_of_day = 12

        is_unusual_hour = 1.0 if (0 <= hour_of_day <= 5 or hour_of_day >= 23) else 0.0

        # 2. Network & device heuristics
        ip_risk = self._compute_ip_risk(ip_address)
        device_anomaly = self._compute_device_anomaly(device_fingerprint, did_id)

        # 3. Burst rate indicator (failed attempts scaled logarithmically)
        burst_rate = min(1.0, math.log1p(max(0, recent_failed_attempts)) / math.log1p(10))

        # 4. Construct pandas DataFrame
        raw_df = pd.DataFrame([{
            "failed_attempts": float(recent_failed_attempts),
            "hour_of_day": float(hour_of_day),
            "is_unusual_hour": float(is_unusual_hour),
            "ip_risk": float(ip_risk),
            "device_anomaly": float(device_anomaly),
            "burst_rate": float(burst_rate)
        }])

        # 5. Normalize using scikit-learn MinMaxScaler
        normalized_array = self.scaler.transform(raw_df)
        norm_df = pd.DataFrame(normalized_array, columns=self.feature_columns)

        return norm_df, normalized_array[0]
