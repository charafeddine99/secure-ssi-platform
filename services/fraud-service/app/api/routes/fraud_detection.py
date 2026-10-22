import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.detection import FraudDetectionRequest, FraudDetectionResponse
from app.ml.pipeline import FeaturePipeline
from app.ml.hybrid_engine import HybridFraudDetector

logger = logging.getLogger("fraud_detection_api")

router = APIRouter(tags=["AI Fraud Detection"])

pipeline = FeaturePipeline()
detector = HybridFraudDetector()


@router.post(
    "/api/fraud_detection",
    response_model=FraudDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate synthetic prototype signals with advisory rules"
)
async def evaluate_fraud_risk(payload: FraudDetectionRequest):
    """
    Evaluates synthetic prototype signals with deterministic rules. This is not
    a trained model and does not determine credential validity or issuer trust.

    Returns:
    - risk_score: Integer between 0 and 100
    - is_fraudulent: A thresholded heuristic flag, advisory only
    """
    try:
        # Validate incoming data constraints
        if not payload.did_id or not payload.did_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload: 'did_id' cannot be empty."
            )

        if payload.recent_failed_attempts < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload: 'recent_failed_attempts' cannot be negative."
            )

        # Feature extraction and normalization for the fixed heuristic rules.
        _, normalized_features = pipeline.process_and_normalize(
            did_id=payload.did_id,
            timestamp=payload.timestamp,
            ip_address=payload.ip_address,
            device_fingerprint=payload.device_fingerprint,
            recent_failed_attempts=payload.recent_failed_attempts
        )

        # Deterministic heuristic evaluation (no trained model is loaded).
        result = detector.evaluate(normalized_features)

        logger.info(
            f"Evaluated DID: {payload.did_id} -> Risk Score: {result['risk_score']} | "
            f"Fraudulent: {result['is_fraudulent']}"
        )

        return FraudDetectionResponse(
            risk_score=result["risk_score"],
            is_fraudulent=result["is_fraudulent"],
            did_id=payload.did_id,
            anomaly_score=result["anomaly_score"],
            reasons=result["reasons"],
            model_version=result["model_version"],
            advisory_only=True,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during fraud evaluation pipeline")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Heuristic risk evaluation could not be completed."
        )
