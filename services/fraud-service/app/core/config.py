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

# Model Ağırlıkları (XGBoost + Autoencoder Hibrit Modeli)
XGB_WEIGHT = float(os.getenv("XGB_WEIGHT", "0.60"))
AE_WEIGHT = float(os.getenv("AE_WEIGHT", "0.40"))
