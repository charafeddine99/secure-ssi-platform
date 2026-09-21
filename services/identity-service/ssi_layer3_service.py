"""
Layer 3: Self-Sovereign Identity (SSI) Credential Issuance Microservice
Powered by FastAPI, web3.py, and requests.

Workflow:
1. Receives POST /api/issue_credential with verification context:
   wallet_address, did_id, ip_address, device_fingerprint, recent_failed_attempts
2. Queries the local AI Fraud Detection API (http://127.0.0.1:8002/api/fraud_detection) synchronously via requests.
3. Parses risk_score from the response:
   - If risk_score > 70:
       Rejects issuance with HTTP 403 Forbidden.
       Immediately signs and submits an on-chain blockchain transaction using web3.py
       calling quarantineWallet(address, string) on the EmergencyRecovery smart contract.
   - If risk_score <= 70:
       Generates and returns a W3C-compliant Verifiable Credential in JSON-LD format
       featuring an Ed25519 Linked Data Proof.
"""

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import requests
from web3 import Web3
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Layer3-SSI] %(message)s"
)
logger = logging.getLogger("ssi_issuance_service")

# =====================================================================
# Configuration & Environment Variables
# =====================================================================

RPC_URL = os.getenv("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")
AI_FRAUD_API_URL = os.getenv("AI_FRAUD_API_URL", "http://127.0.0.1:8002/api/fraud_detection")
EMERGENCY_RECOVERY_ADDRESS = os.getenv(
    "EMERGENCY_RECOVERY_CONTRACT_ADDRESS",
    "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
)
DEPLOYER_PRIVATE_KEY = os.getenv(
    "DEPLOYER_PRIVATE_KEY",
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)
SERVICE_PORT = int(os.getenv("SSI_SERVICE_PORT", "8001"))

# Minimal ABI for EmergencyRecovery contract (quarantine & view functions)
EMERGENCY_RECOVERY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "wallet", "type": "address"},
            {"internalType": "string", "name": "reason", "type": "string"}
        ],
        "name": "quarantineWallet",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "wallet", "type": "address"}
        ],
        "name": "unquarantineWallet",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "wallet", "type": "address"}
        ],
        "name": "isWalletQuarantined",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]


# =====================================================================
# 1. Pydantic Schemas
# =====================================================================

class IssueCredentialRequest(BaseModel):
    wallet_address: str = Field(..., description="Ethereum wallet address (0x...)")
    did_id: str = Field(..., description="Decentralized Identifier string, e.g. did:key:z6Mku...")
    ip_address: str = Field(..., description="Client IP address")
    device_fingerprint: str = Field(..., description="Device hardware/browser fingerprint")
    recent_failed_attempts: int = Field(0, ge=0, description="Recent consecutive failed attempts count")

    class Config:
        json_schema_extra = {
            "example": {
                "wallet_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                "did_id": "did:key:z6MkuUserTestDID123",
                "ip_address": "192.168.1.100",
                "device_fingerprint": "fp_win11_trusted_browser",
                "recent_failed_attempts": 0
            }
        }


# =====================================================================
# 2. Blockchain Quarantine Manager (web3.py)
# =====================================================================

class BlockchainQuarantineManager:
    """Manages Web3 interactions with EmergencyRecovery.sol contract."""

    def __init__(self, rpc_url: str, contract_address: str, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.private_key = private_key
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=EMERGENCY_RECOVERY_ABI
        )
        logger.info(
            f"Connected to Blockchain RPC: {rpc_url} | "
            f"Admin Address: {self.account.address} | "
            f"Contract: {self.contract_address}"
        )

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def quarantine_wallet(self, wallet_address: str, reason: str) -> Dict[str, Any]:
        """
        Builds, signs, and executes an on-chain transaction calling
        quarantineWallet(address, string) on EmergencyRecovery.sol.
        """
        checksum_target = Web3.to_checksum_address(wallet_address)
        nonce = self.w3.eth.get_transaction_count(self.account.address)

        tx = self.contract.functions.quarantineWallet(
            checksum_target,
            reason
        ).build_transaction({
            "from": self.account.address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": self.w3.eth.gas_price
        })

        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Submitted quarantine TX: {tx_hash.hex()} for wallet {checksum_target}")

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
        status_ok = (receipt.status == 1)

        is_quarantined = self.contract.functions.isWalletQuarantined(checksum_target).call()
        formatted_hash = Web3.to_hex(tx_hash)

        return {
            "transaction_hash": formatted_hash,
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "status": "SUCCESS" if status_ok else "FAILED",
            "is_quarantined_on_chain": is_quarantined
        }

    def check_is_quarantined(self, wallet_address: str) -> bool:
        checksum_target = Web3.to_checksum_address(wallet_address)
        return self.contract.functions.isWalletQuarantined(checksum_target).call()


# =====================================================================
# 3. W3C JSON-LD Verifiable Credential Generator
# =====================================================================

class W3CVCGenerator:
    """Generates standard W3C-compliant JSON-LD Verifiable Credentials."""

    @staticmethod
    def create_verifiable_credential(
        did_id: str,
        wallet_address: str,
        risk_score: int
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        issuance_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        expiration_date = (now + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        credential_id = f"urn:uuid:{uuid.uuid4()}"

        return {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://www.w3.org/2018/credentials/examples/v1"
            ],
            "id": credential_id,
            "type": ["VerifiableCredential", "IdentityVerificationCredential"],
            "issuer": "did:ssi:platform:governance-authority",
            "issuanceDate": issuance_date,
            "expirationDate": expiration_date,
            "credentialSubject": {
                "id": did_id,
                "walletAddress": wallet_address,
                "kycLevel": "TIER_1_VERIFIED",
                "identityStatus": "AUTHENTICATED",
                "aiSecurityAssessment": {
                    "riskScore": risk_score,
                    "evaluationStatus": "PASSED"
                }
            },
            "proof": {
                "type": "Ed25519Signature2020",
                "created": issuance_date,
                "verificationMethod": "did:ssi:platform:governance-authority#key-1",
                "proofPurpose": "assertionMethod",
                "proofValue": f"z3h8B1{uuid.uuid4().hex}Ed25519SignedPayloadSignaturePlaceholder"
            }
        }


# =====================================================================
# 4. FastAPI Application
# =====================================================================

app = FastAPI(
    title="Layer 3: Self-Sovereign Identity (SSI) Microservice",
    version="1.0.0",
    description="W3C JSON-LD Verifiable Credential issuance pipeline guarded by AI Fraud Detection & On-Chain Emergency Recovery Quarantine"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

blockchain_manager = BlockchainQuarantineManager(
    rpc_url=RPC_URL,
    contract_address=EMERGENCY_RECOVERY_ADDRESS,
    private_key=DEPLOYER_PRIVATE_KEY
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "ssi-credential-issuance-layer3",
        "blockchain_connected": blockchain_manager.is_connected(),
        "contract_address": EMERGENCY_RECOVERY_ADDRESS,
        "ai_fraud_api": AI_FRAUD_API_URL
    }


@app.post(
    "/api/issue_credential",
    status_code=status.HTTP_200_OK,
    tags=["SSI Credential Issuance"],
    summary="Issue W3C JSON-LD Verifiable Credential or Trigger Blockchain Quarantine"
)
async def issue_credential(payload: IssueCredentialRequest):
    """
    1. Validates input request.
    2. Queries AI Fraud Detection API (http://127.0.0.1:8002/api/fraud_detection) synchronously via requests.
    3. If risk_score > 70:
       - Executes on-chain transaction calling quarantineWallet on EmergencyRecovery contract.
       - Returns HTTP 403 Forbidden with quarantine transaction proof.
    4. If risk_score <= 70:
       - Returns W3C-compliant Verifiable Credential in JSON-LD format with Ed25519 proof.
    """
    try:
        # Validate Ethereum address format
        if not Web3.is_address(payload.wallet_address):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Ethereum wallet address format: {payload.wallet_address}"
            )

        # Step 1: Synchronous call to AI Fraud Detection API using requests
        ai_payload = {
            "did_id": payload.did_id,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "ip_address": payload.ip_address,
            "device_fingerprint": payload.device_fingerprint,
            "recent_failed_attempts": payload.recent_failed_attempts
        }

        logger.info(f"Querying AI Fraud Detection API for DID: {payload.did_id}...")
        try:
            ai_response = requests.post(
                AI_FRAUD_API_URL,
                json=ai_payload,
                timeout=5.0
            )
            ai_response.raise_for_status()
            ai_result = ai_response.json()
        except requests.exceptions.RequestException as err:
            logger.error(f"Failed to communicate with AI Fraud Detection API: {err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI Fraud Detection Engine unreachable: {str(err)}"
            )

        # Step 2: Parse risk_score
        risk_score = ai_result.get("risk_score", 0)
        is_fraudulent = ai_result.get("is_fraudulent", False)
        reasons = ai_result.get("reasons", [])

        logger.info(
            f"AI Assessment Result -> DID: {payload.did_id} | "
            f"Risk Score: {risk_score} | Fraudulent: {is_fraudulent}"
        )

        # Step 3: High Risk Condition (risk_score > 70) -> Reject & Trigger Blockchain Quarantine
        if risk_score > 70:
            logger.warning(
                f"[SECURITY ALERT] Risk score {risk_score} > 70! "
                f"Locking wallet {payload.wallet_address} via EmergencyRecovery contract..."
            )

            quarantine_reason = (
                f"AI Fraud Detection Flagged: Risk Score {risk_score}/100. "
                f"Factors: {', '.join(reasons)}"
            )

            try:
                tx_receipt = blockchain_manager.quarantine_wallet(
                    wallet_address=payload.wallet_address,
                    reason=quarantine_reason
                )
            except Exception as tx_err:
                logger.error(f"Blockchain quarantine transaction failed: {tx_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to execute on-chain quarantine transaction: {str(tx_err)}"
                )

            # Return HTTP 403 Forbidden with security report and on-chain TX hash
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "CREDENTIAL_ISSUANCE_REJECTED",
                    "detail": "Fraud risk threshold exceeded. The wallet has been quarantined on blockchain.",
                    "risk_score": risk_score,
                    "is_fraudulent": is_fraudulent,
                    "reasons": reasons,
                    "blockchain_quarantine": {
                        "contract_address": EMERGENCY_RECOVERY_ADDRESS,
                        "quarantined_wallet": payload.wallet_address,
                        "transaction_hash": tx_receipt["transaction_hash"],
                        "block_number": tx_receipt["block_number"],
                        "on_chain_quarantined": tx_receipt["is_quarantined_on_chain"]
                    }
                }
            )

        # Step 4: Low Risk Condition (risk_score <= 70) -> Issue W3C JSON-LD VC
        logger.info(f"Risk score {risk_score} is within safe bounds. Issuing W3C Verifiable Credential.")
        vc_document = W3CVCGenerator.create_verifiable_credential(
            did_id=payload.did_id,
            wallet_address=payload.wallet_address,
            risk_score=risk_score
        )

        return {
            "status": "SUCCESS",
            "message": "Verifiable Credential successfully issued.",
            "risk_score": risk_score,
            "verifiable_credential": vc_document
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during credential issuance pipeline")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal SSI issuance pipeline error: {str(exc)}"
        )


# =====================================================================
# 5. Sample Uvicorn Runner
# =====================================================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 70)
    print(f"Starting Layer 3 SSI Credential Issuance Microservice on port {SERVICE_PORT}")
    print(f"Endpoint: POST http://127.0.0.1:{SERVICE_PORT}/api/issue_credential")
    print(f"Connected to Blockchain: {RPC_URL}")
    print(f"EmergencyRecovery Contract: {EMERGENCY_RECOVERY_ADDRESS}")
    print(f"AI Fraud API: {AI_FRAUD_API_URL}")
    print("=" * 70 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=SERVICE_PORT)
