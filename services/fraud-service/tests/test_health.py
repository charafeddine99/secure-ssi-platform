from fastapi.testclient import TestClient
from app.main import app
def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "fraud-service"
    assert data["status"] == "healthy"
