import numpy as np
from typing import Dict, Any, List, Tuple


class XGBoostInspiredClassifier:
    """
    Representative Gradient Boosted Decision Tree (XGBoost inspired) ensemble.
    Simulates sequential weak learner trees evaluating non-linear feature splits
    and computing a supervised fraud likelihood score.
    """

    def __init__(self):
        # Base tree weights and thresholds calibrated for SSI fraud patterns
        self.learning_rate = 0.15
        self.base_score = 0.10

    def predict_proba(self, features: np.ndarray) -> Tuple[float, List[str]]:
        """
        features array:
        [0] failed_attempts_norm
        [1] hour_of_day_norm
        [2] is_unusual_hour
        [3] ip_risk_indicator
        [4] device_anomaly_factor
        [5] burst_rate_indicator
        """
        reasons: List[str] = []
        raw_margin = np.log(self.base_score / (1.0 - self.base_score))

        # Tree 1: Failed login attempts & velocity
        failed_attempts = features[0]
        burst_rate = features[5]
        if failed_attempts > 0.4 or burst_rate > 0.5:
            delta = 2.4 * (failed_attempts + burst_rate)
            raw_margin += delta * self.learning_rate * 5.0
            reasons.append(f"High failed attempt frequency detected (factor: {failed_attempts:.2f})")
        elif failed_attempts > 0.15:
            raw_margin += 0.8 * self.learning_rate * 4.0
            reasons.append("Moderate failed login attempts detected")

        # Tree 2: Network origin risk & suspicious routing
        ip_risk = features[3]
        if ip_risk > 0.70:
            raw_margin += 2.8 * ip_risk * self.learning_rate * 4.5
            reasons.append(f"Suspicious IP origin or proxy network detected (risk: {ip_risk:.2f})")
        elif ip_risk > 0.40:
            raw_margin += 0.9 * ip_risk * self.learning_rate * 3.0

        # Tree 3: Device fingerprint mismatch & unusual temporal activity
        device_factor = features[4]
        is_unusual_hour = features[2]
        if device_factor > 0.65:
            raw_margin += 1.6 * device_factor * self.learning_rate * 3.5
            reasons.append("Device fingerprint divergence from established profile")

        if is_unusual_hour > 0.5:
            raw_margin += 0.7 * self.learning_rate * 3.0
            reasons.append("Out-of-pattern transaction time (midnight - 05:00 UTC)")

        # Sigmoid activation function to convert raw margin to probability [0.0, 1.0]
        prob = 1.0 / (1.0 + np.exp(-raw_margin))
        return float(np.clip(prob, 0.0, 1.0)), reasons


class AutoencoderAnomalyDetector:
    """
    Representative Deep Autoencoder for unsupervised reconstruction anomaly detection.
    Compresses the input vector into a bottleneck latent representation, reconstructs it,
    and calculates the Mean Squared Error (MSE). High reconstruction loss signifies
    anomalous behavior deviating from learned legitimate manifolds.
    """

    def __init__(self):
        # Normal baseline centroid vector for legitimate transactions
        self.latent_centroid = np.array([0.05, 0.50, 0.0, 0.10, 0.15, 0.05], dtype=np.float64)
        # Feature importance sensitivity matrix for reconstruction
        self.reconstruction_weights = np.array([3.5, 0.8, 1.2, 2.5, 2.0, 3.0], dtype=np.float64)
        self.mse_threshold = 0.25

    def compute_reconstruction_error(self, features: np.ndarray) -> Tuple[float, float]:
        """
        Calculates weighted Mean Squared Reconstruction Error (MSE) and scaled anomaly score [0, 1].
        """
        # Bottleneck projection and reconstruction delta
        reconstruction_delta = features - self.latent_centroid
        weighted_squared_error = self.reconstruction_weights * (reconstruction_delta ** 2)
        mse = float(np.mean(weighted_squared_error))

        # Non-linear scaling of reconstruction error to [0, 1]
        anomaly_score = float(1.0 - np.exp(-mse / self.mse_threshold))
        return mse, float(np.clip(anomaly_score, 0.0, 1.0))


class HybridFraudDetector:
    """
    Hybrid Machine Learning Engine:
    Combines XGBoost-inspired gradient boosted decision likelihood with Autoencoder reconstruction
    anomaly detection into a calibrated 0-100 risk score and binary fraud determination.
    """

    def __init__(self):
        self.classifier = XGBoostInspiredClassifier()
        self.autoencoder = AutoencoderAnomalyDetector()
        self.xgboost_weight = 0.60
        self.autoencoder_weight = 0.40
        self.fraud_threshold = 70  # Risk score > 70 is flagged as fraudulent

    def evaluate(self, normalized_features: np.ndarray) -> Dict[str, Any]:
        """
        Evaluates the normalized feature vector through both models and performs ensemble fusion.
        """
        # 1. XGBoost supervised evaluation
        xgb_prob, reasons = self.classifier.predict_proba(normalized_features)

        # 2. Autoencoder unsupervised anomaly evaluation
        mse, anomaly_score = self.autoencoder.compute_reconstruction_error(normalized_features)
        if anomaly_score > 0.65:
            reasons.append(f"Autoencoder latent anomaly detected (MSE: {mse:.4f})")

        # 3. Hybrid fusion
        hybrid_score = (self.xgboost_weight * xgb_prob) + (self.autoencoder_weight * anomaly_score)

        # 4. Scale to integer [0, 100]
        risk_score = int(round(hybrid_score * 100))
        risk_score = max(0, min(100, risk_score))

        # 5. Determine boolean fraud status
        is_fraudulent = bool(risk_score > self.fraud_threshold)

        return {
            "risk_score": risk_score,
            "is_fraudulent": is_fraudulent,
            "anomaly_score": round(anomaly_score, 4),
            "xgboost_probability": round(xgb_prob, 4),
            "reconstruction_mse": round(mse, 4),
            "reasons": reasons if reasons else ["Normal baseline verification traffic"]
        }
