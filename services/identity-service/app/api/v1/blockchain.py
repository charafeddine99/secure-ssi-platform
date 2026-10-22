"""Blockchain Anchoring and Verification API Endpoints.

Provides public and authorized status check endpoints for on-chain integrity anchors,
contract statuses, and transaction receipts.
Zero sensitive signer secrets, private keys, or PII exposed.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.dependencies import (
    get_blockchain_anchor_repository,
    get_blockchain_bridge,
)
from app.domain.blockchain_anchor import BlockchainAnchorRecord
from app.infrastructure.blockchain.web3_bridge import BlockchainBridge
from app.infrastructure.persistence.blockchain_anchor_repository import (
    MongoBlockchainAnchorRepository,
)

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


class BlockchainStatusResponse(BaseModel):
    connected: bool
    network: str
    chainId: int
    contracts: dict[str, str]
    currentBlockNumber: int | None = None


class BlockchainAnchorResponse(BaseModel):
    anchorId: str
    eventType: str
    eventHash: str
    contractType: str
    contractAddress: str
    network: str
    chainId: int
    status: str
    createdAt: str
    subjectId: str | None = None
    txHash: str | None = None
    blockNumber: int | None = None
    confirmedAt: str | None = None
    errorMessage: str | None = None
    retryCount: int = 0


def _to_response(rec: BlockchainAnchorRecord) -> BlockchainAnchorResponse:
    return BlockchainAnchorResponse(
        anchorId=rec.anchor_id,
        eventType=rec.event_type.value,
        eventHash=rec.event_hash,
        contractType=rec.contract_type,
        contractAddress=rec.contract_address,
        network=rec.network,
        chainId=rec.chain_id,
        status=rec.status.value,
        createdAt=rec.created_at.isoformat(),
        subjectId=rec.subject_id,
        txHash=rec.tx_hash,
        blockNumber=rec.block_number,
        confirmedAt=rec.confirmed_at.isoformat() if rec.confirmed_at else None,
        errorMessage=rec.error_message,
        retryCount=rec.retry_count,
    )


@router.get("/status", response_model=BlockchainStatusResponse)
def get_blockchain_status(
    bridge: Annotated[BlockchainBridge, Depends(get_blockchain_bridge)],
) -> BlockchainStatusResponse:
    connected = bridge.is_connected()
    block_num = None
    if connected:
        try:
            block_num = bridge.w3.eth.block_number
        except Exception:
            pass

    return BlockchainStatusResponse(
        connected=connected,
        network=bridge.settings.network_name,
        chainId=bridge.settings.chain_id,
        contracts={
            "DIDRegistry": bridge.settings.did_registry_address,
            "RevocationRegistry": bridge.settings.revocation_registry_address,
            "EmergencyRecovery": bridge.settings.emergency_recovery_address,
            "AuditLogger": bridge.settings.audit_logger_address,
        },
        currentBlockNumber=block_num,
    )


@router.get("/contracts")
def get_contracts_directory(
    bridge: Annotated[BlockchainBridge, Depends(get_blockchain_bridge)],
) -> dict[str, Any]:
    connected = bridge.is_connected()
    configured_contracts = [
        (
            "DIDRegistry.sol",
            bridge.settings.did_registry_address,
            "Anchors DID document digests.",
            ["registerDID", "updateVCHash", "getDIDRecord", "isDIDRegistered"],
        ),
        (
            "RevocationRegistry.sol",
            bridge.settings.revocation_registry_address,
            "Optional integrity anchoring for status-list and revocation digests.",
            ["anchorStatusList", "revokeCredential", "isCredentialRevoked", "getStatusListAnchor"],
        ),
        (
            "EmergencyRecovery.sol",
            bridge.settings.emergency_recovery_address,
            "Guardian recovery contract configuration; not used as the credential-validity authority.",
            ["configureGuardians", "initiateRecovery", "approveRecovery", "quarantineWallet", "isWalletQuarantined"],
        ),
        (
            "AuditLogger.sol",
            bridge.settings.audit_logger_address,
            "Optional digest-only event anchoring.",
            ["logEvent", "getEventCount", "getEvent"],
        ),
    ]

    contracts = []
    for name, address, purpose, methods in configured_contracts:
        deployment_verified: bool | None = None
        if not address:
            contract_status = "NOT_CONFIGURED"
        elif not connected:
            contract_status = "CONFIGURED_ONLY"
        else:
            try:
                deployment_verified = bool(bridge.w3.eth.get_code(address))
                contract_status = "DEPLOYED" if deployment_verified else "NO_CODE_AT_ADDRESS"
            except Exception:
                contract_status = "UNVERIFIED"

        contracts.append(
            {
                "name": name,
                "address": address or "",
                "purpose": purpose,
                "methods": methods,
                "status": contract_status,
                "deploymentVerified": deployment_verified,
            }
        )

    return {
        "status": "SUCCESS",
        "connected": connected,
        "network": bridge.settings.network_name,
        "chainId": bridge.settings.chain_id,
        "contracts": contracts,
    }


@router.get("/anchors", response_model=list[BlockchainAnchorResponse])
def list_anchors(
    repo: Annotated[MongoBlockchainAnchorRepository, Depends(get_blockchain_anchor_repository)],
    limit: int = 50,
) -> list[BlockchainAnchorResponse]:
    records = repo.list_all(limit=limit)
    return [_to_response(r) for r in records]


@router.get("/anchors/{anchor_id}", response_model=BlockchainAnchorResponse)
def get_anchor_by_id(
    anchor_id: str,
    repo: Annotated[MongoBlockchainAnchorRepository, Depends(get_blockchain_anchor_repository)],
) -> BlockchainAnchorResponse:
    rec = repo.get_by_id(anchor_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blockchain anchor '{anchor_id}' not found.",
        )
    return _to_response(rec)


@router.get("/anchors/by-hash/{event_hash}", response_model=BlockchainAnchorResponse)
def get_anchor_by_hash(
    event_hash: str,
    repo: Annotated[MongoBlockchainAnchorRepository, Depends(get_blockchain_anchor_repository)],
) -> BlockchainAnchorResponse:
    rec = repo.get_by_event_hash(event_hash)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blockchain anchor for hash '{event_hash}' not found.",
        )
    return _to_response(rec)


@router.get("/anchors/by-subject/{subject_id:path}", response_model=BlockchainAnchorResponse)
def get_latest_anchor_by_subject(
    subject_id: str,
    repo: Annotated[MongoBlockchainAnchorRepository, Depends(get_blockchain_anchor_repository)],
) -> BlockchainAnchorResponse:
    rec = repo.get_latest_by_subject(subject_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No blockchain anchors found for subject '{subject_id}'.",
        )
    return _to_response(rec)
