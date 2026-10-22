"""Blockchain configuration settings for the Secure SSI Platform.

Loads configuration from environment variables or local deployment artifacts,
ensuring strict decoupling and zero hardcoded secrets.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class BlockchainSettings:
    rpc_url: str = "http://127.0.0.1:8545"
    chain_id: int = 1337
    private_key: str = ""
    did_registry_address: str = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    revocation_registry_address: str = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
    emergency_recovery_address: str = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
    audit_logger_address: str = "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9"
    timeout_seconds: float = 8.0
    network_name: str = "localhost"
    enabled: bool = True


def load_blockchain_settings(
    environ: Mapping[str, str] | None = None,
    deployment_path: Path | None = None,
) -> BlockchainSettings:
    values = os.environ if environ is None else environ

    # Attempt to read dynamic deployed-contracts.json if present
    addresses = {}
    dep_file = deployment_path
    if dep_file is None:
        # Search workspace paths for deployed-contracts.json
        source_path = Path(__file__).resolve()
        candidates = [
            parent / "blockchain" / "deployed-contracts.json"
            for parent in source_path.parents
        ]
        candidates.append(Path.cwd() / "blockchain" / "deployed-contracts.json")
        for c in candidates:
            if c.is_file():
                dep_file = c
                break

    if dep_file and dep_file.is_file():
        try:
            with open(dep_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                contracts = data.get("contracts", {})
                addresses = {
                    "DIDRegistry": contracts.get("DIDRegistry"),
                    "RevocationRegistry": contracts.get("RevocationRegistry"),
                    "EmergencyRecovery": contracts.get("EmergencyRecovery"),
                    "AuditLogger": contracts.get("AuditLogger"),
                }
        except Exception:
            pass

    return BlockchainSettings(
        rpc_url=values.get("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545"),
        chain_id=int(values.get("BLOCKCHAIN_CHAIN_ID", "1337")),
        private_key=values.get("BLOCKCHAIN_PRIVATE_KEY", ""),
        did_registry_address=values.get(
            "DID_REGISTRY_ADDRESS",
            addresses.get("DIDRegistry") or "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        ),
        revocation_registry_address=values.get(
            "REVOCATION_REGISTRY_ADDRESS",
            addresses.get("RevocationRegistry") or "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        ),
        emergency_recovery_address=values.get(
            "EMERGENCY_RECOVERY_ADDRESS",
            addresses.get("EmergencyRecovery") or "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
        ),
        audit_logger_address=values.get(
            "AUDIT_LOGGER_ADDRESS",
            addresses.get("AuditLogger") or "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
        ),
        timeout_seconds=float(values.get("BLOCKCHAIN_TIMEOUT_SECONDS", "8.0")),
        network_name=values.get("BLOCKCHAIN_NETWORK", "localhost"),
        enabled=values.get("BLOCKCHAIN_ENABLED", "false").lower() in ("true", "1", "yes"),
    )
