# Sprint 16: Blockchain Anchoring Bridge Specification & Architecture

> **Implementation Context**: Academic SSI platform prototype / reference implementation.
> **Scope**: Integrity anchoring layer for decentralized identifiers, W3C Bitstring status lists, on-chain emergency response, and security audit digests.

> **Current G10 execution note (15 October 2026):** this document's earlier prose is historical where it conflicts with `docs/implementation/SECURE_SSI_PLATFORM_FINAL_IMPLEMENTATION_PLAN.md`. The current bridge anchors approved digests only. DID and status-list keys are hashed before contract calls. A quarantine event is a digest in `AuditLogger`; it does not call the contract's address-and-reason quarantine method. Chain state is optional and never establishes credential validity or status. The current scoped G10 contract, local receipt, and unanchored-policy evidence is in [test evidence](implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md).

---

## 1. Architectural Overview & MongoDB Decoupling

The Secure SSI Platform utilizes an **asymmetric dual-layer persistence model**:

```
                       AUTHORITATIVE APPLICATION LAYER
                         [MongoDB Persistence Store]
                         (Credentials, Status Lists, DIDs,
                          Holder Wallets, Audit Events)
                                      │
                         Deterministic Canonicalization
                                 (RFC 8785)
                                      │
                            SHA-256 Digest (32 bytes)
                                      │
                       INTEGRITY / ANCHORING LAYER
                         [Python Web3 RPC Bridge]
                                      │
                    Local Hardhat JSON-RPC (Port 8545)
                                      │
  ┌───────────────────────┬───────────┴───────────┬───────────────────────┐
  ▼                       ▼                       ▼                       ▼
DIDRegistry.sol   RevocationRegistry.sol  EmergencyRecovery.sol     AuditLogger.sol
(did:key / doc)   (W3C Bitstring roots)  (AI-Quarantine Lockout)  (Security Digests)
  │                       │                       │                       │
  └───────────────────────┴───────────┬───────────┴───────────────────────┘
                                      ▼
                        On-Chain Transaction Receipt
                        (tx_hash, block_number, status)
                                      │
                                      ▼
                        MongoDB `blockchain_anchors`
                               Record Store
```

### Core Separation of Concerns
* **MongoDB**: Remains the **authoritative application persistence layer**. All Verifiable Credentials, DID records, Status List bitstrings, user profiles, cryptographic key metadata, and complete audit event details live in MongoDB.
* **Blockchain (Layer 1)**: Operates purely as a **tamper-evident integrity anchor**. The blockchain proves *when* a state existed and *verifies* that off-chain records have not been tampered with.
* **Fail-Open Resilience**: Blockchain is **not an availability bottleneck**. If the node is offline, a transaction is reverted, or a receipt times out, credential issuance and verification remain independent. Anchor records use `OFFLINE`, `FAILED`, `SUBMITTED`, or `SKIPPED` as applicable; a presentation reports `blockchainAnchored: false` when no confirmed receipt exists. A transaction hash is retained only when the node accepted a transaction. No alerting or retry worker is claimed.

---

## 2. On-Chain vs. Off-Chain Data Boundary (Non-PII Policy)

Under strict European privacy regulations (GDPR) and academic security standards, **no Personally Identifiable Information (PII) or sensitive keys may ever enter the blockchain**:

| Category | Allowed On-Chain? | Representation |
| :--- | :---: | :--- |
| **Private Keys / Seed Phrases** | ❌ **NEVER** | Maintained strictly in holder device hardware or KMS/HSM |
| **Verifiable Credentials** | ❌ **NEVER** | Stored in Holder Wallet / Issuer MongoDB |
| **Identity Attributes (Name, DoB, Email)** | ❌ **NEVER** | Kept in off-chain verifiable credentials |
| **Shamir Secret Shares / Recovery Data** | ❌ **NEVER** | Encrypted and distributed directly to designated guardians |
| **DID Document Hashes** | ✅ **YES** | Deterministic SHA-256 digest (`bytes32`); DID registry key is also hashed |
| **W3C Status List Root Hashes** | ✅ **YES** | Deterministic SHA-256 digest (`bytes32`) of bitstring bytes; status-list identifier is hashed |
| **Quarantine Event** | ✅ **YES** | Digest and `ACCOUNT_QUARANTINED` category through `AuditLogger`; no wallet address or reason is passed |
| **Audit Event Digests** | ✅ **YES** | SHA-256 hash (`bytes32`) and event category enum (`uint8`) |

The application-side quarantine lock remains process-local prototype state. Its optional chain digest does not persist or define the lock and is not a credential-status authority.

---

## 3. Smart Contracts & Access Control

### 1. `DIDRegistry.sol`
* **Address**: `0x5FbDB2315678afecb367f032d93F642f64180aa3`
* **Purpose**: Binds a hash of a DID key to a credential/document hash; the raw DID is not sent to the contract.
* **Access Control**: Identity owner controls updates (`onlyDIDOwner` modifier). Unauthorized actors cannot overwrite or rebind another organization's or holder's DID.
* **Reentrancy**: Protected by OpenZeppelin `ReentrancyGuard`.

### 2. `RevocationRegistry.sol`
* **Address**: `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`
* **Purpose**: Anchors W3C Bitstring Status List root digests (`anchorStatusList`) and individual credential revocations (`revokeCredential`).
* **Idempotency**: Prevents duplicate revocations with reverts (`"RevocationRegistry: Zaten iptal edilmis"`). Application bridge checks `isCredentialRevoked` before submitting to avoid redundant gas costs.
* **Authorization**: Credential revocation is restricted to the contract owner. The deployer owns the contract initially; the Identity Service transaction signer must therefore match that owner for on-chain revocation writes. A non-owner call reverts and leaves the credential hash unchanged. This is a single-owner prototype policy, not a multi-issuer role registry.
* **Deployment boundary**: This source change does not alter an already deployed, non-upgradeable contract. Redeploy the contract and configure its new address before relying on owner-only revocation on any existing network; do not treat old deployed bytecode as protected by this source change.

### 3. `EmergencyRecovery.sol`
* **Address**: `0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0`
* **Purpose**: Prototype guardian recovery (2-of-3); the current optional integrity bridge does not invoke its address-and-reason quarantine method.
* **Authority Principle**: Blockchain does not calculate or override a risk score. Credential verification and status do not depend on chain availability.

### 4. `AuditLogger.sol`
* **Address**: `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9`
* **Purpose**: Append-only log of SHA-256 security digests across categories:
  * `IDENTITY_ACTION` (0)
  * `CREDENTIAL_ISSUED` (1)
  * `CREDENTIAL_VERIFIED` (2)
  * `FRAUD_DETECTED` (3)
  * `ACCOUNT_QUARANTINED` (4)
  * `RECOVERY_TRIGGERED` (5)
  * `KEY_ROTATED` (6)

---

## 4. Anchor Lifecycle & State Machine

Every blockchain anchoring request creates a persistent MongoDB record in `blockchain_anchors` with the following lifecycle:

```
    [PENDING] ──────► [SUBMITTED] ──────► [CONFIRMED]
        │                   │
        ├──► [OFFLINE]
        ├──► [FAILED] ◄─────┘
        └──► [SKIPPED] (matching state; no new receipt)
```

* **`PENDING`**: Request generated, canonical hash computed, ready for RPC transmission.
* **`SUBMITTED`**: Transaction signed and broadcast to the mempool; transaction hash recorded.
* **`CONFIRMED`**: Transaction included in a block; receipt verified with `status == 1`. Block number and confirmation timestamp stored.
* **`SUBMITTED` after receipt timeout**: The RPC accepted a transaction hash, but no receipt was available before timeout. This is not a confirmation.
* **`OFFLINE`**: The optional RPC or required contract is unavailable. No transaction was submitted and no transaction hash is reported.
* **`SKIPPED`**: An on-chain read found the requested state already present; no synthetic transaction hash or receipt is recorded.
* **`FAILED`**: A submitted transaction reverted or another anchoring operation failed. A real hash/block is retained only when the transaction was submitted/mined.

---

## 5. Environment Configuration

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `BLOCKCHAIN_RPC_URL` | `http://127.0.0.1:8545` | JSON-RPC provider endpoint |
| `BLOCKCHAIN_CHAIN_ID` | `1337` | Local Hardhat chain ID (`11155111` for Sepolia) |
| `BLOCKCHAIN_PRIVATE_KEY` | empty | Optional signer key; supply a secret explicitly only for a disposable local test network |
| `DID_REGISTRY_ADDRESS` | `0x5FbDB2315678afecb367f032d93F642f64180aa3` | Deployed `DIDRegistry.sol` |
| `REVOCATION_REGISTRY_ADDRESS`| `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512` | Deployed `RevocationRegistry.sol` |
| `EMERGENCY_RECOVERY_ADDRESS` | `0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0` | Deployed `EmergencyRecovery.sol` |
| `AUDIT_LOGGER_ADDRESS` | `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9` | Deployed `AuditLogger.sol` |
| `BLOCKCHAIN_TIMEOUT_SECONDS` | `8.0` | Transaction receipt timeout before fail-open |
| `BLOCKCHAIN_ENABLED` | `false` | Master switch for optional blockchain anchoring |

---

## 6. Local Node Execution & Deployment Verification

1. **Install dependencies**:
   ```bash
   cd blockchain
   npm install
   ```

2. **Run contract test suite**:
   ```bash
   npx hardhat test
   ```

3. **Start local Hardhat JSON-RPC node**:
   ```bash
   npx hardhat node --hostname 127.0.0.1 --port 8545
   ```

4. **Deploy contracts**:
   ```bash
   npx hardhat run scripts/deploy.ts --network localhost
   ```
   Deployment metadata is automatically written to `blockchain/deployed-contracts.json`.

5. **Execute Backend Verification**:
   ```bash
   python run_tests.py
   ```
