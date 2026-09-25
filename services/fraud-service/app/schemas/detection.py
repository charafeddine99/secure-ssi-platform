from typing import Optional, List
from pydantic import BaseModel, Field


class FraudDetectionRequest(BaseModel):
    """
    JSON request payload for the AI Fraud Detection evaluation.
    """
    did_id: str = Field(..., description="Decentralized Identifier string, e.g. did:key:z6Mku...")
    timestamp: int = Field(..., description="Unix epoch timestamp in seconds")
    ip_address: str = Field(..., description="Origin IPv4 or IPv6 client address")
    device_fingerprint: str = Field(..., description="Client device hardware/browser fingerprint hash")
    recent_failed_attempts: int = Field(..., ge=0, description="Count of recent consecutive failed attempts")

    class Config:
        json_schema_extra = {
            "example": {
                "did_id": "did:ssi:alice:001",
                "timestamp": 1726938000,
                "ip_address": "185.220.101.5",
                "device_fingerprint": "fp_chrome_win11_a93f12e8",
                "recent_failed_attempts": 5
            }
        }


class FraudDetectionResponse(BaseModel):
    """
    JSON response payload returned by the AI Fraud Detection endpoint.
    """
    risk_score: int = Field(..., ge=0, le=100, description="Evaluated risk score between 0 and 100")
    is_fraudulent: bool = Field(..., description="True if risk exceeds the security threshold (>70)")
    did_id: Optional[str] = Field(None, description="Echo of evaluated DID")
    anomaly_score: Optional[float] = Field(None, description="Autoencoder reconstruction anomaly score in [0.0, 1.0]")
    reasons: Optional[List[str]] = Field(None, description="Diagnostic risk rationale factors")
