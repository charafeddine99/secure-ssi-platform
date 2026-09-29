"""Unit tests for Blockchain API routes (/api/v1/blockchain/*)."""

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import (
    get_blockchain_anchor_repository,
    get_blockchain_bridge,
)
from app.domain.blockchain_anchor import (
    AnchorEventType,
    BlockchainAnchorRecord,
    BlockchainAnchorStatus,
)
from app.main import app
from tests.support.fake_mongo import FakeDatabase
from app.infrastructure.persistence.blockchain_anchor_repository import (
    MongoBlockchainAnchorRepository,
)
from app.infrastructure.blockchain.web3_bridge import BlockchainBridge
from app.config.blockchain_settings import BlockchainSettings


@pytest.fixture
def blockchain_client():
    db = FakeDatabase()
    repo = MongoBlockchainAnchorRepository(db["blockchain_anchors"])
    settings = BlockchainSettings(
        rpc_url="http://127.0.0.1:8545",
        network_name="localhost",
        chain_id=1337,
    )
    bridge = BlockchainBridge(settings=settings, repository=repo)

    app.dependency_overrides[get_blockchain_anchor_repository] = lambda: repo
    app.dependency_overrides[get_blockchain_bridge] = lambda: bridge

    client = TestClient(app)
    yield client, repo

    app.dependency_overrides.clear()


def test_get_blockchain_status(blockchain_client):
    client, _ = blockchain_client
    response = client.get("/api/v1/blockchain/status")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    assert data["network"] == "localhost"
    assert data["chainId"] == 1337
    assert "contracts" in data
    assert "DIDRegistry" in data["contracts"]
    assert "RevocationRegistry" in data["contracts"]
    assert "EmergencyRecovery" in data["contracts"]
    assert "AuditLogger" in data["contracts"]


def test_get_anchor_by_id_and_hash(blockchain_client):
    client, repo = blockchain_client

    record = BlockchainAnchorRecord.create_pending(
        event_type=AnchorEventType.DID_DOCUMENT,
        event_hash="0x" + "c" * 64,
        contract_type="DIDRegistry",
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        network="localhost",
        chain_id=1337,
        subject_id="did:key:z6MkuApiTest",
    )
    confirmed = record.mark_confirmed("0x" + "d" * 64, block_number=55)
    repo.save(confirmed)

    # 1. By ID
    res1 = client.get(f"/api/v1/blockchain/anchors/{record.anchor_id}")
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["anchorId"] == record.anchor_id
    assert d1["status"] == "CONFIRMED"
    assert d1["txHash"] == "0x" + "d" * 64
    assert d1["blockNumber"] == 55

    # 2. By Hash
    res2 = client.get(f"/api/v1/blockchain/anchors/by-hash/{record.event_hash}")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["anchorId"] == record.anchor_id

    # 3. By Subject
    res3 = client.get(f"/api/v1/blockchain/anchors/by-subject/{record.subject_id}")
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["anchorId"] == record.anchor_id

    # 4. Not Found
    res4 = client.get("/api/v1/blockchain/anchors/non-existent-anchor-id")
    assert res4.status_code == 404
