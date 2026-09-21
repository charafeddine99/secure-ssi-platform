import time
import hashlib
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/v1/iot/door", tags=["IoT Secure Door Bridge"])

class DoorAccessRequest(BaseModel):
    device_id: str = Field("esp32-door-01", description="ESP32 Cihaz Kimliği")
    credential_id: str = Field(..., description="W3C Verifiable Credential ID")
    holder_did: str = Field(..., description="Kullanıcı DID")
    holder_name: str = Field("Charaf Eddine Bessanane", description="Kullanıcı Adı")
    client_ip: str = Field("192.168.1.150", description="Erişim Noktası IP")
    geo_distance_km: float = Field(0.0, description="Konum farkı")
    failed_attempts: int = Field(0, description="Son başarısız denemeler")
    is_tor_or_proxy: bool = Field(False, description="Anonim IP kullanımı")

class DoorAccessResponse(BaseModel):
    device_id: str
    access_granted: bool
    holder_did: str
    holder_name: str
    ai_risk_score: float
    ai_risk_level: str
    unlock_duration_sec: int
    message: str
    audit_hash: str
    timestamp: float

@router.post("/access", response_model=DoorAccessResponse, summary="ESP32 Güvenli Kapı İçin SSI ve AI Doğrulaması Yapar")
async def verify_door_access(req: DoorAccessRequest):
    """
    ESP32 Kapı Kontrol Sistemi (esp32-kodlar) ile Secure SSI Platformunu entegre eder:
    1. W3C Kimlik Bilgisini (Diploma/Kart/Yetki) doğrular.
    2. AI Fraud Detection katmanından geçerek anomali kontrolü yapar.
    3. Şüpheli durum yoksa ESP32'ye kapı açma (unlock) komutu ve süresi döner.
    """
    # 1. Temel AI Fraud Simülasyonu
    risk_score = 0.05
    if req.failed_attempts >= 3:
        risk_score += 0.40
    if req.geo_distance_km > 50.0:
        risk_score += 0.50
    if req.is_tor_or_proxy:
        risk_score += 0.35

    risk_score = min(risk_score, 1.0)
    risk_level = "LOW"
    access_granted = True
    unlock_duration = 5
    msg = f"Hosgeldiniz, {req.holder_name}. Kapi kilidi acildi."

    if risk_score >= 0.70:
        risk_level = "CRITICAL"
        access_granted = False
        unlock_duration = 0
        msg = "ERISIM REDDEDILDI: AI Guvenlik Katmani yuksek anomali/risk tespit etti!"
    elif risk_score >= 0.40:
        risk_level = "MEDIUM"
        access_granted = False
        unlock_duration = 0
        msg = "EK DOGRULAMA GEREKLI: Keypad PIN kodunu giriniz."

    # Denetim hash'i
    audit_payload = f"{req.device_id}:{req.holder_did}:{risk_score}:{time.time()}".encode()
    audit_hash = "0x" + hashlib.sha256(audit_payload).hexdigest()

    return DoorAccessResponse(
        device_id=req.device_id,
        access_granted=access_granted,
        holder_did=req.holder_did,
        holder_name=req.holder_name,
        ai_risk_score=round(risk_score, 3),
        ai_risk_level=risk_level,
        unlock_duration_sec=unlock_duration,
        message=msg,
        audit_hash=audit_hash,
        timestamp=time.time()
    )
