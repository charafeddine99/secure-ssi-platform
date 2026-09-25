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

def test_correlation_id_middleware():
    # 1. Automatic generation
    res = client.get("/health")
    assert "X-Correlation-ID" in res.headers
    auto_id = res.headers["X-Correlation-ID"]
    assert len(auto_id) > 10

    # 2. Preservation of incoming correlation ID
    custom_id = "test-corr-id-998877"
    res2 = client.get("/health", headers={"X-Correlation-ID": custom_id})
    assert res2.headers.get("X-Correlation-ID") == custom_id

def test_security_headers_middleware():
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

def test_payload_size_limit():
    large_payload = b"X" * (1024 * 1024 + 10)  # > 1 MB
    res = client.post("/api/v1/identity/credentials", content=large_payload)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

