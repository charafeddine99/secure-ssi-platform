from types import SimpleNamespace

from app.api.v1.blockchain import get_contracts_directory


def _bridge(*, connected: bool, code_by_address: dict[str, bytes] | None = None):
    addresses = {
        "did_registry_address": "0x0000000000000000000000000000000000000001",
        "revocation_registry_address": "0x0000000000000000000000000000000000000002",
        "emergency_recovery_address": "0x0000000000000000000000000000000000000003",
        "audit_logger_address": "0x0000000000000000000000000000000000000004",
    }
    settings = SimpleNamespace(network_name="test-network", chain_id=31337, **addresses)
    queried: list[str] = []

    def get_code(address: str) -> bytes:
        queried.append(address)
        return (code_by_address or {}).get(address, b"")

    bridge = SimpleNamespace(
        settings=settings,
        is_connected=lambda: connected,
        w3=SimpleNamespace(eth=SimpleNamespace(get_code=get_code)),
    )
    return bridge, queried


def test_offline_directory_does_not_claim_contracts_are_active_or_deployed():
    bridge, queried = _bridge(connected=False)

    result = get_contracts_directory(bridge)

    assert result["status"] == "SUCCESS"
    assert result["connected"] is False
    assert len(result["contracts"]) == 4
    assert {item["status"] for item in result["contracts"]} == {"CONFIGURED_ONLY"}
    assert all(item["deploymentVerified"] is None for item in result["contracts"])
    assert queried == []


def test_connected_directory_verifies_deployed_code_per_address():
    deployed = "0x0000000000000000000000000000000000000001"
    bridge, queried = _bridge(connected=True, code_by_address={deployed: b"\x60\x00"})

    result = get_contracts_directory(bridge)

    assert result["connected"] is True
    assert result["contracts"][0]["status"] == "DEPLOYED"
    assert result["contracts"][0]["deploymentVerified"] is True
    assert result["contracts"][1]["status"] == "NO_CODE_AT_ADDRESS"
    assert result["contracts"][1]["deploymentVerified"] is False
    assert len(queried) == 4
