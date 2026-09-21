from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_gateway_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "healthy"

def test_system_status_aggregation():
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["gateway_status"] == "ONLINE"
    assert "services" in data
    assert "identity_service" in data["services"]
    assert "fraud_service" in data["services"]
    assert "recovery_service" in data["services"]

def test_proxy_route_structure():
    # Servis kapalıyken 503 veya 502 düzgün hata dönmeli (çökmemeli)
    response = client.get("/api/v1/fraud/stats")
    assert response.status_code in (200, 502, 503)
