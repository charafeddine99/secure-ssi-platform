from fastapi.testclient import TestClient
from app.api.routes import proxy as proxy_routes
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

def test_system_status_marks_optional_chain_and_persistence_truthfully(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url):
            if url.endswith("/health"):
                return FakeResponse(200)
            if url.endswith("/api/v1/blockchain/status"):
                return FakeResponse(200, {"connected": False})
            if url.endswith("/api/v1/database/stats"):
                return FakeResponse(503)
            raise AssertionError(f"Unexpected health dependency URL: {url}")

    monkeypatch.setattr(
        proxy_routes.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeClient(),
    )

    response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    data = response.json()
    assert data["services"]["blockchain_node"] == "DEGRADED"
    assert data["blockchain"]["connected"] is False
    assert data["database"] == {"status": "UNAVAILABLE"}
    assert data["system_health"] == "PARTIAL"

def test_proxy_route_structure(monkeypatch):
    # Keep this offline-path test independent from whichever service happens
    # to be listening on localhost:8002 on the developer's machine.
    requested = []

    class UnavailableClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, *, method, url, **_kwargs):
            requested.append((method, url))
            raise proxy_routes.httpx.ConnectError("fraud service unavailable")

    monkeypatch.setattr(
        proxy_routes.httpx,
        "AsyncClient",
        lambda **_kwargs: UnavailableClient(),
    )

    response = client.get("/api/v1/fraud/stats")
    assert response.status_code == 503
    assert requested == [
        ("GET", "http://127.0.0.1:8002/api/v1/fraud/stats")
    ]

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

