from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_iot_door_access_granted():
    payload = {
        "device_id": "esp32-door-01",
        "credential_id": "urn:uuid:subu-diploma-2026-001",
        "holder_did": "did:key:z6MkuBesnaStudent2026",
        "holder_name": "Charaf Eddine Bessanane",
        "client_ip": "192.168.1.150",
        "geo_distance_km": 0.0,
        "failed_attempts": 0,
        "is_tor_or_proxy": False
    }
    response = client.post("/api/v1/iot/door/access", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["access_granted"] is True
    assert data["unlock_duration_sec"] == 5
    assert data["ai_risk_level"] == "LOW"
    assert "Hosgeldiniz" in data["message"]
    assert data["audit_hash"].startswith("0x")

def test_iot_door_access_rejected_anomalous_risk():
    payload = {
        "device_id": "esp32-door-01",
        "credential_id": "urn:uuid:subu-diploma-2026-001",
        "holder_did": "did:key:z6MkuStolenKey",
        "holder_name": "Suspicious User",
        "client_ip": "185.220.101.9",
        "geo_distance_km": 500.0, # Büyük mesafe sapması
        "failed_attempts": 4,     # Çoklu hatalı deneme
        "is_tor_or_proxy": True
    }
    response = client.post("/api/v1/iot/door/access", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["access_granted"] is False
    assert data["unlock_duration_sec"] == 0
    assert data["ai_risk_level"] == "CRITICAL"
    assert "ERISIM REDDEDILDI" in data["message"]
