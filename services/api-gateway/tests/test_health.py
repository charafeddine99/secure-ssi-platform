from fastapi.testclient import TestClient
from app.main import app
from app.core.config import APP_VERSION
def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "api-gateway", "status": "healthy", "version": APP_VERSION}
