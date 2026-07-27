from fastapi.testclient import TestClient
from app.main import app
def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "fraud-service", "status": "healthy", "version": "0.1.0"}
