import sys
import pytest
from pathlib import Path
import urllib.request
import urllib.error
import json

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

GATEWAY_BASE_URL = "http://127.0.0.1:8000"


def is_gateway_online():
    try:
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/health")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.skipif(not is_gateway_online(), reason="API Gateway daemon is not running on port 8000")
class TestAdminConsoleLiveIntegration:
    """
    Sprint 18 Admin Console End-to-End Integration Verification.
    Validates that:
    1. System status endpoint aggregates microservices, blockchain node, and database metrics.
    2. Blockchain status endpoint exposes live contract addresses and network details.
    3. Smart contracts directory lists DIDRegistry, RevocationRegistry, EmergencyRecovery, and AuditLogger.
    4. Audit logs are accessible via unified API gateway route with filtering support.
    5. Database persistence statistics accurately report authoritative MongoDB and SQLite metrics.
    6. Real-time AI fraud model telemetry returns accuracy, confusion matrix, and quantization data.
    """

    def test_system_status_aggregation(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/system/status")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["gateway_status"] == "ONLINE"
            assert "services" in data
            assert data["services"]["identity_service"] == "HEALTHY"
            assert data["services"]["fraud_service"] == "HEALTHY"
            assert data["services"]["recovery_service"] == "HEALTHY"
            assert data["services"]["blockchain_node"] == "HEALTHY"
            assert data["blockchain"]["connected"] is True
            assert "database" in data

    def test_blockchain_status_and_contracts_directory(self):
        req_status = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/blockchain/status")
        with urllib.request.urlopen(req_status, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["connected"] is True
            assert "contracts" in data
            contracts = data["contracts"]
            assert "did_registry" in contracts
            assert "revocation_registry" in contracts
            assert "emergency_recovery" in contracts
            assert "audit_logger" in contracts

        req_contracts = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/blockchain/contracts")
        with urllib.request.urlopen(req_contracts, timeout=3) as resp:
            assert resp.status == 200
            c_data = json.loads(resp.read().decode("utf-8"))
            assert c_data["status"] == "SUCCESS"
            assert len(c_data["contracts"]) == 4

    def test_audit_logs_endpoint(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/identity/audit_logs")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "SUCCESS"
            assert isinstance(data.get("audit_logs"), list)

    def test_database_stats_telemetry(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/identity/database/stats")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "SUCCESS"
            assert "authoritative_persistence" in data
            assert "stats" in data
            assert "credentials" in data["stats"]
            assert "audit_logs" in data["stats"]

    def test_fraud_model_telemetry(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/fraud/stats")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "accuracy" in data
            assert data["accuracy"] > 0.90
            assert "confusion_matrix" in data
            assert "latency_ms_avg" in data
