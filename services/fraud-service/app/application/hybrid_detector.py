import math
import uuid
from datetime import datetime, timezone
from typing import Tuple, List, Dict
from app.core.config import (
    RISK_THRESHOLD_LOW,
    RISK_THRESHOLD_MEDIUM,
    RISK_THRESHOLD_HIGH,
    RISK_THRESHOLD_QUARANTINE,
    RULE_SCORE_WEIGHT,
    BEHAVIORAL_DEVIATION_WEIGHT
)
from app.schemas.fraud import FraudEvaluationRequest, FraudEvaluationResponse, HeuristicBreakdown

class HybridFraudDetector:
    """
    Deterministic rule-based heuristic scorer for the synthetic prototype.

    The implementation is not a trained ML model. It combines explicit risk
    rules with a weighted behavioral-deviation formula and remains advisory.
    """

    MODEL_VERSION = "rule-heuristic-v1"
    RISK_SIGNALS = [
        "impossible_travel",
        "failed_attempt_velocity",
        "presentation_frequency",
        "device_fingerprint_mismatch",
        "tor_or_proxy_indicator",
    ]

    def __init__(self):
        self._quarantined_dids: Dict[str, Dict] = {}
        self.stats = {
            "model_type": "Deterministic rule-based heuristic engine",
            "model_version": self.MODEL_VERSION,
            "model_status": "NOT_TRAINED",
            "evaluation_status": "NO_INDEPENDENT_LABELLED_EVALUATION",
            "dataset_label": "[DEMO LAB / SYNTHETIC]",
            "advisory_only": True,
            "risk_signals": list(self.RISK_SIGNALS),
        }

    def _extract_features(self, req: FraudEvaluationRequest) -> Tuple[List[float], List[str]]:
        reasons: List[str] = []

        # 1. Hız ve İmkansız Seyahat (Impossible Travel) Kontrolü
        hours = max(req.time_since_last_action_sec / 3600.0, 0.001)
        velocity_kmh = req.geo_distance_km / hours
        geo_risk = 0.0
        if velocity_kmh > 800.0 and req.geo_distance_km > 100.0:
            geo_risk = 0.98
            reasons.append(f"İmkansız seyahat tespit edildi: {req.geo_distance_km:.1f} km mesafe {hours*60:.1f} dakikada katedilemez ({velocity_kmh:.0f} km/h).")
        elif req.geo_distance_km > 300.0:
            geo_risk = min(req.geo_distance_km / 1000.0, 0.75)
            reasons.append(f"Olağan dışı coğrafi sıçrama: {req.geo_distance_km:.1f} km.")

        # 2. Başarısız Denemeler (Brute-force / Credential Stuffing)
        failure_risk = 0.0
        if req.failed_attempts >= 5:
            failure_risk = 0.95
            reasons.append(f"Kritik sayıda başarısız oturum denemesi ({req.failed_attempts} kez).")
        elif req.failed_attempts >= 3:
            failure_risk = 0.70
            reasons.append(f"Şüpheli başarısız deneme sayısı ({req.failed_attempts} kez).")
        elif req.failed_attempts > 0:
            failure_risk = 0.30

        # 3. İşlem Sıklığı Anomali Kontrolü
        freq_risk = 0.0
        if req.presentation_frequency_10m > 15:
            freq_risk = 0.85
            reasons.append(f"Aşırı yüksek işlem sıklığı: 10 dakikada {req.presentation_frequency_10m} istek.")
        elif req.presentation_frequency_10m > 5:
            freq_risk = 0.50
            reasons.append(f"Normalin üzerinde işlem sıklığı: {req.presentation_frequency_10m} istek.")

        # 4. Cihaz Parmak İzi Uyuşmazlığı
        device_risk = 0.0
        if not req.device_fingerprint_match:
            device_risk = 0.70
            reasons.append("Bilinmeyen veya eşleşmeyen cihaz parmak izi.")

        # 5. Tor / Anonim Proxy Kontrolü
        proxy_risk = 0.0
        if req.is_tor_or_proxy:
            proxy_risk = 0.85
            reasons.append("İstek bilinen bir Tor çıkış noktası veya anonimleştirici proxy üzerinden geldi.")

        feature_vector = [geo_risk, failure_risk, freq_risk, device_risk, proxy_risk]
        return feature_vector, reasons

    def _behavioral_deviation(self, features: List[float]) -> Tuple[float, float]:
        """Return a deterministic weighted deviation heuristic, not ML inference."""
        weights = [0.25, 0.25, 0.20, 0.15, 0.15]
        weighted_deviation = math.sqrt(sum(w * (f ** 2) for w, f in zip(weights, features)))
        deviation_score = 1.0 / (1.0 + math.exp(-8.0 * (weighted_deviation - 0.25)))
        return round(weighted_deviation, 4), round(deviation_score, 4)

    def _rule_score(self, features: List[float]) -> float:
        """Apply explicit weighted rules and fixed interaction multipliers."""
        geo, fail, freq, dev, proxy = features
        raw_score = (0.35 * geo) + (0.30 * fail) + (0.25 * freq) + (0.15 * dev) + (0.30 * proxy)

        # Çoklu risk kombinasyonları çarpanı (Adversarial pattern)
        if geo > 0.8 and dev > 0.5:
            raw_score += 0.30
        if fail > 0.6 and freq > 0.4:
            raw_score += 0.25
        if freq > 0.7:
            raw_score += 0.35
        if proxy > 0.7:
            raw_score += 0.20

        score = 1.0 - math.exp(-2.5 * raw_score)
        return round(min(max(score, 0.0), 1.0), 4)

    def evaluate(self, request: FraudEvaluationRequest) -> FraudEvaluationResponse:
        features, reasons = self._extract_features(request)
        _, behavioral_deviation_score = self._behavioral_deviation(features)
        rule_score = self._rule_score(features)

        combined_risk = round(
            (RULE_SCORE_WEIGHT * rule_score)
            + (BEHAVIORAL_DEVIATION_WEIGHT * behavioral_deviation_score),
            4,
        )

        # Karar eşikleri
        if combined_risk >= RISK_THRESHOLD_QUARANTINE:
            risk_level = "CRITICAL"
            recommended_action = "QUARANTINE_ACCOUNT"
            is_anomaly = True
        elif combined_risk >= RISK_THRESHOLD_HIGH:
            risk_level = "HIGH"
            recommended_action = "MANUAL_REVIEW"
            is_anomaly = True
        elif combined_risk >= RISK_THRESHOLD_MEDIUM:
            risk_level = "MEDIUM"
            recommended_action = "REQUIRE_STEP_UP_AUTH"
            is_anomaly = True
        else:
            risk_level = "LOW"
            recommended_action = "ALLOW"
            is_anomaly = False
            if not reasons:
                reasons.append("Tüm davranış parametreleri normal profil ile uyumlu.")

        return FraudEvaluationResponse(
            evaluation_id=str(uuid.uuid4()),
            did=request.did,
            risk_score=combined_risk,
            risk_level=risk_level,
            is_anomaly=is_anomaly,
            recommended_action=recommended_action,
            reasons=reasons,
            heuristic_breakdown=HeuristicBreakdown(
                rule_score=rule_score,
                behavioral_deviation=behavioral_deviation_score,
                combined_score=combined_risk,
            ),
            model_version=self.MODEL_VERSION,
            risk_signals=list(self.RISK_SIGNALS),
            advisory_only=True,
            evaluated_at=datetime.now(timezone.utc).isoformat()
        )

    def quarantine(self, did: str, reason: str) -> Dict:
        entry = {
            "did": did,
            "is_quarantined": True,
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason
        }
        self._quarantined_dids[did] = entry
        return entry

    def release_quarantine(self, did: str) -> bool:
        if did in self._quarantined_dids:
            del self._quarantined_dids[did]
            return True
        return False

    def is_quarantined(self, did: str) -> bool:
        return did in self._quarantined_dids

    def get_quarantine_info(self, did: str) -> Dict:
        return self._quarantined_dids.get(did, {"did": did, "is_quarantined": False})

detector = HybridFraudDetector()
