import os
from pathlib import Path

SERVICE_NAME = "fraud-service"
APP_VERSION = os.getenv("APP_VERSION", "0.2.0")

# Dizinler
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True, parents=True)

# Risk Skor Eşikleri (Rapordaki güvenlik ve karantina kuralları)
RISK_THRESHOLD_LOW = float(os.getenv("RISK_THRESHOLD_LOW", "0.25"))
RISK_THRESHOLD_MEDIUM = float(os.getenv("RISK_THRESHOLD_MEDIUM", "0.50"))
RISK_THRESHOLD_HIGH = float(os.getenv("RISK_THRESHOLD_HIGH", "0.75"))
RISK_THRESHOLD_QUARANTINE = float(os.getenv("RISK_THRESHOLD_QUARANTINE", "0.80"))

# Weights for the deterministic rule-based heuristic. Legacy environment
# variable names remain accepted for local compatibility; they do not
# represent trained model components.
RULE_SCORE_WEIGHT = float(os.getenv("RULE_SCORE_WEIGHT", os.getenv("XGB_WEIGHT", "0.60")))
BEHAVIORAL_DEVIATION_WEIGHT = float(os.getenv("BEHAVIORAL_DEVIATION_WEIGHT", os.getenv("AE_WEIGHT", "0.40")))

_cors_origins = os.getenv("FRAUD_CORS_ORIGINS", "")
CORS_ORIGINS = [
    origin.strip()
    for origin in _cors_origins.split(",")
    if origin.strip()
]
if not CORS_ORIGINS:
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5178",
        "http://127.0.0.1:5178",
    ]
