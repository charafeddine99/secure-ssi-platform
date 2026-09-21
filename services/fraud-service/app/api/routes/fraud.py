from fastapi import APIRouter, HTTPException, status
from app.schemas.fraud import (
    FraudEvaluationRequest,
    FraudEvaluationResponse,
    QuarantineRequest,
    QuarantineResponse,
    ModelStatsResponse
)
from app.application.hybrid_detector import detector

router = APIRouter(prefix="/api/v1/fraud", tags=["Fraud Detection & Security"])

@router.post(
    "/evaluate",
    response_model=FraudEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Kimlik doğrulama veya işlem için AI risk değerlendirmesi yapar"
)
async def evaluate_transaction(request: FraudEvaluationRequest):
    """
    SSI doğrulama veya işlem talebini hibrit AI motoruyla (XGBoost + Autoencoder) analiz eder.
    Risk skoru, anomali durumu ve önerilen güvenlik aksiyonunu (ALLOW, REQUIRE_STEP_UP_AUTH, MANUAL_REVIEW, QUARANTINE_ACCOUNT) döner.
    """
    try:
        return detector.evaluate(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI risk değerlendirmesi sırasında hata: {str(exc)}"
        )

@router.get(
    "/stats",
    response_model=ModelStatsResponse,
    summary="AI modelinin performans, doğruluk ve konfüzyon matrisi istatistiklerini getirir"
)
async def get_model_stats():
    """
    Tasarım raporundaki %94.3 hedef doğruluk, F1-score, Precision, Recall ve Confusion Matrix metriklerini sunar.
    """
    return detector.stats

@router.post(
    "/quarantine",
    response_model=QuarantineResponse,
    summary="Yüksek riskli bir hesabı manuel veya otomatik karantinaya alır"
)
async def quarantine_account(request: QuarantineRequest):
    """
    Şüpheli DID'yi karantina havuzuna ekler; tüm doğrulama ve sunum işlemlerini kilitler.
    """
    result = detector.quarantine(request.did, request.reason)
    return QuarantineResponse(
        did=result["did"],
        is_quarantined=True,
        status="QUARANTINED",
        quarantined_at=result["quarantined_at"],
        reason=result["reason"]
    )

@router.get(
    "/quarantine/{did}",
    response_model=QuarantineResponse,
    summary="Bir DID'nin karantina durumunu sorgular"
)
async def get_quarantine_status(did: str):
    info = detector.get_quarantine_info(did)
    return QuarantineResponse(
        did=did,
        is_quarantined=info.get("is_quarantined", False),
        status="QUARANTINED" if info.get("is_quarantined") else "ACTIVE",
        quarantined_at=info.get("quarantined_at"),
        reason=info.get("reason")
    )

@router.delete(
    "/quarantine/{did}",
    summary="Karantinadaki bir hesabın kilidini kaldırır"
)
async def release_account_quarantine(did: str):
    released = detector.release_quarantine(did)
    if not released:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{did} tanımlayıcısına sahip aktif bir karantina kaydı bulunamadı."
        )
    return {"did": did, "status": "RELEASED", "message": "Hesap karantinadan çıkarıldı."}
