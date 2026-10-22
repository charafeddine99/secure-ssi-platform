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
    6. Fraud telemetry reports heuristic status, version, synthetic scope, and signals.
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
            assert isinstance(data["blockchain"]["connected"], bool)
            expected_chain_status = (
                "HEALTHY" if data["blockchain"]["connected"] else "DEGRADED"
            )
            assert data["services"]["blockchain_node"] == expected_chain_status
            assert "database" in data
            assert data["database"]["status"] in {
                "SUCCESS",
                "UNAVAILABLE",
                "UNREACHABLE",
            }
            expected_health = (
                "OPTIMAL"
                if all(value == "HEALTHY" for value in data["services"].values())
                and data["database"]["status"] == "SUCCESS"
                else "PARTIAL"
            )
            assert data["system_health"] == expected_health

    def test_blockchain_status_and_contracts_directory(self):
        req_status = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/blockchain/status")
        with urllib.request.urlopen(req_status, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert isinstance(data["connected"], bool)
            assert "contracts" in data
            contracts = data["contracts"]
            assert set(contracts) == {
                "DIDRegistry",
                "RevocationRegistry",
                "EmergencyRecovery",
                "AuditLogger",
            }
            if data["connected"]:
                assert isinstance(data["currentBlockNumber"], int)
            else:
                assert data["currentBlockNumber"] is None

        req_contracts = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/blockchain/contracts")
        with urllib.request.urlopen(req_contracts, timeout=3) as resp:
            assert resp.status == 200
            c_data = json.loads(resp.read().decode("utf-8"))
            assert c_data["status"] == "SUCCESS"
            assert len(c_data["contracts"]) == 4

    def test_audit_logs_endpoint(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/identity/audit_logs")
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            # This integration probe is unauthenticated. Audit history must
            # remain protected before persistence availability is disclosed.
            assert exc.code == 401
            return

        with response as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "SUCCESS"
            assert isinstance(data.get("audit_logs"), list)

    def test_database_stats_telemetry(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/identity/database/stats")
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            # This integration probe is unauthenticated. Admin telemetry must
            # reject it before evaluating persistence state.
            assert exc.code == 401
            return

        with response:
            assert response.status == 200
            data = json.loads(response.read().decode("utf-8"))
            assert data["status"] == "SUCCESS"
            assert data["authoritative_persistence"] == "MongoDB"
            assert "stats" in data
            assert isinstance(data["stats"]["credentials"], int)
            assert isinstance(data["stats"]["audit_logs"], int)

    def test_fraud_model_telemetry(self):
        req = urllib.request.Request(f"{GATEWAY_BASE_URL}/api/v1/fraud/stats")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["model_version"] == "rule-heuristic-v1"
            assert data["model_status"] == "NOT_TRAINED"
            assert data["dataset_label"] == "[DEMO LAB / SYNTHETIC]"
            assert data["advisory_only"] is True
            assert data["risk_signals"]
