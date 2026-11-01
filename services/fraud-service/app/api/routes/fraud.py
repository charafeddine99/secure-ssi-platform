from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.fraud import (
    FraudEvaluationRequest,
    FraudEvaluationResponse,
    QuarantineRequest,
    QuarantineResponse,
    ModelStatsResponse,
    PlatformSecurityEvent,
    EventIngestionResponse,
    EventBatchIngestionRequest,
    EventBatchIngestionResponse,
)
from app.application.hybrid_detector import detector
from app.ml.feature_store import feature_store
from app.ml.synthetic_dataset import generate_synthetic_ssi_dataset, calculate_evaluation_metrics
from app.core.security import (
    FraudPrincipal,
    require_admin,
    require_authenticated,
    require_internal_service,
)

router = APIRouter(prefix="/api/v1/fraud", tags=["Fraud Detection & Security"])

@router.post(
    "/evaluate",
    response_model=FraudEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthetic prototype event için advisory heuristic risk değerlendirmesi yapar"
)
async def evaluate_transaction(
    request: FraudEvaluationRequest,
    _principal: FraudPrincipal = Depends(require_authenticated),
):
    """
    Applies deterministic rules to synthetic prototype event signals. This is
    not a trained model and does not establish credential validity or trust.
    """
    try:
        return detector.evaluate(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Heuristic risk evaluation could not be completed."
        )

@router.get(
    "/stats",
    response_model=ModelStatsResponse,
    summary="Returns heuristic engine version and measured-evaluation status"
)
async def get_model_stats():
    return detector.stats

@router.post(
    "/quarantine",
    response_model=QuarantineResponse,
    summary="Records an explicit prototype quarantine action"
)
async def quarantine_account(
    request: QuarantineRequest,
    _principal: FraudPrincipal = Depends(require_admin),
):
    """
    Şüpheli DID'yi yalnızca bu Fraud Service sürecinin yerel karantina havuzuna ekler.
    Bu işlem Identity Service statüsünü veya credential geçerliliğini değiştirmez.
    """
    result = detector.quarantine(request.did, request.reason)
    return QuarantineResponse(
        did=result["did"],
        is_quarantined=True,
        status="QUARANTINED",
        quarantined_at=result["quarantined_at"],
        reason=result["reason"],
        effect_scope="fraud-service-process-local",
    )

@router.get(
    "/quarantine/{did}",
    response_model=QuarantineResponse,
    summary="Bir DID'nin karantina durumunu sorgular"
)
async def get_quarantine_status(
    did: str,
    _principal: FraudPrincipal = Depends(require_admin),
):
    info = detector.get_quarantine_info(did)
    return QuarantineResponse(
        did=did,
        is_quarantined=info.get("is_quarantined", False),
        status="QUARANTINED" if info.get("is_quarantined") else "ACTIVE",
        quarantined_at=info.get("quarantined_at"),
        reason=info.get("reason"),
        effect_scope="fraud-service-process-local",
    )

@router.delete(
    "/quarantine/{did}",
    summary="Karantinadaki bir hesabın kilidini kaldırır"
)
async def release_account_quarantine(
    did: str,
    _principal: FraudPrincipal = Depends(require_admin),
):
    released = detector.release_quarantine(did)
    if not released:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{did} tanımlayıcısına sahip aktif bir karantina kaydı bulunamadı."
        )
    return {
        "did": did,
        "status": "RELEASED",
        "message": "Hesap karantinadan çıkarıldı.",
        "effect_scope": "fraud-service-process-local",
    }


@router.post(
    "/events",
    response_model=EventIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Platform güvenlik olayını (Section 14) Feature Store'a kaydeder"
)
async def ingest_security_event(
    event: PlatformSecurityEvent,
    _principal: FraudPrincipal = Depends(require_internal_service),
):
    """
    Section 14 olaylarını (LOGIN, LOGIN_FAILED, CREDENTIAL_PRESENTED, vb.) Feature Store'a kaydeder
    ve anlık kayan pencere (sliding-window) davranış özetini döner.
    """
    summary = feature_store.ingest_event(
        event_id=event.event_id,
        event_type=event.event_type,
        did=event.did,
        client_ip=event.client_ip,
        user_agent=event.user_agent,
        device_fingerprint=event.device_fingerprint,
        timestamp=event.timestamp,
        metadata=event.metadata,
    )

    return EventIngestionResponse(
        status="INGESTED",
        event_id=event.event_id,
        did=event.did,
        event_type=event.event_type,
        sliding_window_summary=summary,
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/events/batch",
    response_model=EventBatchIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Toplu platform güvenlik olaylarını Feature Store'a aktarır"
)
async def ingest_batch_security_events(
    batch: EventBatchIngestionRequest,
    _principal: FraudPrincipal = Depends(require_internal_service),
):
    for event in batch.events:
        summary = feature_store.ingest_event(
            event_id=event.event_id,
            event_type=event.event_type,
            did=event.did,
            client_ip=event.client_ip,
            user_agent=event.user_agent,
            device_fingerprint=event.device_fingerprint,
            timestamp=event.timestamp,
            metadata=event.metadata,
        )
    return EventBatchIngestionResponse(
        status="BATCH_INGESTED",
        ingested_count=len(batch.events),
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/history/{did}",
    summary="Bir DID'nin kayan pencere davranışsal metriklerini döner"
)
async def get_did_behavioral_history(
    did: str,
    _principal: FraudPrincipal = Depends(require_admin),
):
    features = feature_store.get_features(did)
    return {
        "did": did,
        "features": features,
        "is_quarantined": detector.is_quarantined(did),
    }


@router.get(
    "/dataset/metrics",
    summary="Computes a deterministic heuristic replay diagnostic on generated synthetic events"
)
async def evaluate_synthetic_dataset(
    _principal: FraudPrincipal = Depends(require_admin),
):
    """
    Diagnostic only: metrics describe this fixed, generated synthetic replay.
    They are not training metrics or evidence of real-world generalization.
    """
    df = generate_synthetic_ssi_dataset(n_samples=1000, fraud_ratio=0.30, seed=42)
    y_true = df["is_fraudulent"].to_numpy()

    y_probs = []
    y_preds = []

    for idx, row in df.iterrows():
        req = FraudEvaluationRequest(
            did=f"did:key:z6MkuSynthetic_{idx}",
            action="presentation_verification",
            client_ip="185.220.101.5" if row["is_tor_or_proxy"] else "192.168.1.100",
            user_agent="SyntheticAgent",
            failed_attempts=int(row["failed_attempts"]),
            geo_distance_km=float(row["geo_distance_km"]),
            time_since_last_action_sec=float(row["time_since_last_action_sec"]),
            presentation_frequency_10m=int(row["presentation_frequency_10m"]),
            device_fingerprint_match=bool(row["device_fingerprint_match"]),
            is_tor_or_proxy=bool(row["is_tor_or_proxy"]),
        )
        res = detector.evaluate(req)
        score = res.risk_score
        y_probs.append(score)
        y_preds.append(1 if score >= 0.50 else 0)

    import numpy as np
    metrics = calculate_evaluation_metrics(y_true, np.array(y_preds), np.array(y_probs))
    metrics["model_version"] = detector.MODEL_VERSION
    metrics["model_type"] = detector.stats["model_type"]
    metrics["dataset_label"] = "[DEMO LAB / SYNTHETIC]"
    metrics["evaluation_scope"] = "deterministic heuristic replay on generated events"
    metrics["trained_model"] = False
    metrics["dataset_description"] = (
        "1000 generated examples (700 normal, 300 attack-pattern events); "
        "seed=42; not representative of production traffic."
    )
    return metrics

