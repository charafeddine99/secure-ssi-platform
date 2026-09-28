from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class FraudEvaluationRequest(BaseModel):
    did: str = Field(..., description="Kullanıcı veya Holder DID tanımlayıcısı")
    action: str = Field("presentation_verification", description="İşlem türü: login, presentation_verification, recovery_request vb.")
    client_ip: str = Field("127.0.0.1", description="İstemci IP adresi")
    user_agent: str = Field("Mozilla/5.0", description="İstemci tarayıcı / cihaz bilgisi")
    timestamp: Optional[float] = Field(None, description="Unix zaman damgası")
    failed_attempts: int = Field(0, description="Son 10 dakikadaki başarısız deneme sayısı")
    geo_distance_km: float = Field(0.0, description="Son başarılı konum ile mevcut konum arası mesafe (km)")
    time_since_last_action_sec: float = Field(60.0, description="Son işlemden bu yana geçen saniye")
    presentation_frequency_10m: int = Field(1, description="Son 10 dakikadaki sunum / doğrulama sayısı")
    device_fingerprint: str = Field("default-device", description="Cihaz parmak izi özeti")
    device_fingerprint_match: bool = Field(True, description="Kayıtlı cihaz ile eşleşme durumu")
    is_tor_or_proxy: bool = Field(False, description="IP'nin bilinen anonimleştirici/VPN/Tor olup olmadığı")

class ModelBreakdown(BaseModel):
    xgboost_score: float
    autoencoder_recon_error: float
    autoencoder_score: float

class FraudEvaluationResponse(BaseModel):
    evaluation_id: str
    did: str
    risk_score: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    is_anomaly: bool
    recommended_action: str  # "ALLOW", "REQUIRE_STEP_UP_AUTH", "MANUAL_REVIEW", "QUARANTINE_ACCOUNT"
    reasons: List[str]
    model_breakdown: ModelBreakdown
    evaluated_at: str

class QuarantineRequest(BaseModel):
    did: str
    reason: str

class QuarantineResponse(BaseModel):
    did: str
    is_quarantined: bool
    status: str
    quarantined_at: Optional[str] = None
    reason: Optional[str] = None

class ModelStatsResponse(BaseModel):
    model_type: str = "Hybrid (XGBoost + Autoencoder)"
    accuracy: float = 0.943
    precision: float = 0.938
    recall: float = 0.948
    f1_score: float = 0.943
    confusion_matrix: Dict[str, int] = {
        "true_positives": 474,
        "true_negatives": 469,
        "false_positives": 31,
        "false_negatives": 26
    }
    sample_count: int = 1000
    latency_ms_avg: float = 4.2
    model_quantization: str = "FP16"
    last_trained: str


class PlatformSecurityEvent(BaseModel):
    event_id: str = Field(..., description="Tekil olay kimliği (UUID)")
    event_type: str = Field(
        ...,
        description="Olay türü: LOGIN, LOGIN_FAILED, WALLET_CREATED, CREDENTIAL_RECEIVED, CREDENTIAL_PRESENTED, VERIFICATION_FAILED, RECOVERY_STARTED, KEY_ROTATED, REVOKED",
    )
    did: str = Field(..., description="İlgili Holder veya kullanıcı DID'si")
    client_ip: str = Field("127.0.0.1", description="Kaynak IP adresi")
    user_agent: str = Field("Mozilla/5.0", description="İstemci User-Agent")
    device_fingerprint: str = Field("default-device", description="Cihaz parmak izi")
    timestamp: Optional[float] = Field(None, description="Unix zaman damgası")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Ek bağlam bilgileri")


class EventIngestionResponse(BaseModel):
    status: str = "INGESTED"
    event_id: str
    did: str
    event_type: str
    sliding_window_summary: Dict[str, Any]
    ingested_at: str


class EventBatchIngestionRequest(BaseModel):
    events: List[PlatformSecurityEvent]


class EventBatchIngestionResponse(BaseModel):
    status: str = "BATCH_INGESTED"
    ingested_count: int
    ingested_at: str

