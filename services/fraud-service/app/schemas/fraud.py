from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class FraudEvaluationRequest(BaseModel):
    did: str = Field(..., min_length=1, max_length=512, description="Kullanıcı veya Holder DID tanımlayıcısı")
    action: str = Field("presentation_verification", max_length=64, description="İşlem türü: login, presentation_verification, recovery_request vb.")
    client_ip: str = Field("127.0.0.1", max_length=64, description="İstemci IP adresi")
    user_agent: str = Field("Mozilla/5.0", max_length=512, description="İstemci tarayıcı / cihaz bilgisi")
    timestamp: Optional[float] = Field(None, ge=0, description="Unix zaman damgası")
    failed_attempts: int = Field(0, ge=0, le=10000, description="Son 10 dakikadaki başarısız deneme sayısı")
    geo_distance_km: float = Field(0.0, ge=0, le=40075, description="Son başarılı konum ile mevcut konum arası mesafe (km)")
    time_since_last_action_sec: float = Field(60.0, ge=0, le=31536000, description="Son işlemden bu yana geçen saniye")
    presentation_frequency_10m: int = Field(1, ge=0, le=10000, description="Son 10 dakikadaki sunum / doğrulama sayısı")
    device_fingerprint: str = Field("default-device", max_length=512, description="Cihaz parmak izi özeti")
    device_fingerprint_match: bool = Field(True, description="Kayıtlı cihaz ile eşleşme durumu")
    is_tor_or_proxy: bool = Field(False, description="IP'nin bilinen anonimleştirici/VPN/Tor olup olmadığı")

class HeuristicBreakdown(BaseModel):
    rule_score: float
    behavioral_deviation: float
    combined_score: float

class FraudEvaluationResponse(BaseModel):
    evaluation_id: str
    did: str
    risk_score: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    is_anomaly: bool
    recommended_action: str  # "ALLOW", "REQUIRE_STEP_UP_AUTH", "MANUAL_REVIEW", "QUARANTINE_ACCOUNT"
    reasons: List[str]
    heuristic_breakdown: HeuristicBreakdown
    model_version: str
    risk_signals: List[str] = Field(default_factory=list)
    advisory_only: bool = True
    evaluated_at: str

class QuarantineRequest(BaseModel):
    did: str = Field(..., min_length=1, max_length=512)
    reason: str = Field(..., min_length=1, max_length=512)

class QuarantineResponse(BaseModel):
    did: str
    is_quarantined: bool
    status: str
    quarantined_at: Optional[str] = None
    reason: Optional[str] = None
    effect_scope: str = "fraud-service-process-local"

class ModelStatsResponse(BaseModel):
    model_type: str
    model_version: str
    model_status: str
    evaluation_status: str
    dataset_label: str
    advisory_only: bool
    risk_signals: List[str]


class PlatformSecurityEvent(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=128, description="Tekil olay kimliği (UUID)")
    event_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Olay türü: LOGIN, LOGIN_FAILED, WALLET_CREATED, CREDENTIAL_RECEIVED, CREDENTIAL_PRESENTED, VERIFICATION_FAILED, RECOVERY_STARTED, KEY_ROTATED, REVOKED",
    )
    did: str = Field(..., min_length=1, max_length=512, description="İlgili Holder veya kullanıcı DID'si")
    client_ip: str = Field("127.0.0.1", max_length=64, description="Kaynak IP adresi")
    user_agent: str = Field("Mozilla/5.0", max_length=512, description="İstemci User-Agent")
    device_fingerprint: str = Field("default-device", max_length=512, description="Cihaz parmak izi")
    timestamp: Optional[float] = Field(None, ge=0, description="Unix zaman damgası")
    metadata: Dict[str, Any] = Field(default_factory=dict, max_length=32, description="Ek bağlam bilgileri; hassas değerler saklanmaz")


class EventIngestionResponse(BaseModel):
    status: str = "INGESTED"
    event_id: str
    did: str
    event_type: str
    sliding_window_summary: Dict[str, Any]
    ingested_at: str


class EventBatchIngestionRequest(BaseModel):
    events: List[PlatformSecurityEvent] = Field(..., min_length=1, max_length=100)


class EventBatchIngestionResponse(BaseModel):
    status: str = "BATCH_INGESTED"
    ingested_count: int
    ingested_at: str

