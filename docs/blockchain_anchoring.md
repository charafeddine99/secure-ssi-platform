# Sprint 16: Blockchain Anchoring Bridge Specification & Architecture

> **Implementation Context**: Academic SSI platform prototype / reference implementation.
> **Scope**: Integrity anchoring layer for decentralized identifiers, W3C Bitstring status lists, on-chain emergency response, and security audit digests.

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
* **Fail-Open Resilience**: Blockchain is **not an availability bottleneck**. If the blockchain node is offline, slow, or fails to confirm a transaction, credential issuance and verification **never fail**. Instead, the anchor state is marked `FAILED` or `RETRYABLE` in MongoDB, and administrative alerts are triggered.

---

## 2. On-Chain vs. Off-Chain Data Boundary (Non-PII Policy)

Under strict European privacy regulations (GDPR) and academic security standards, **no Personally Identifiable Information (PII) or sensitive keys may ever enter the blockchain**:

| Category | Allowed On-Chain? | Representation |
| :--- | :---: | :--- |
| **Private Keys / Seed Phrases** | ❌ **NEVER** | Maintained strictly in holder device hardware or KMS/HSM |
| **Verifiable Credentials** | ❌ **NEVER** | Stored in Holder Wallet / Issuer MongoDB |
| **Identity Attributes (Name, DoB, Email)** | ❌ **NEVER** | Kept in off-chain verifiable credentials |
| **Shamir Secret Shares / Recovery Data** | ❌ **NEVER** | Encrypted and distributed directly to designated guardians |
| **DID Document Hashes** | ✅ **YES** | Deterministic SHA-256 hash (`bytes32`) |
| **W3C Status List Root Hashes** | ✅ **YES** | Deterministic SHA-256 hash (`bytes32`) of bitstring bytes |
| **Quarantine Status & Wallet Address** | ✅ **YES** | Ethereum address (`address`) and quarantine flag |
| **Audit Event Digests** | ✅ **YES** | SHA-256 hash (`bytes32`) and event category enum (`uint8`) |

---

## 3. Smart Contracts & Access Control

### 1. `DIDRegistry.sol`
* **Address**: `0x5FbDB2315678afecb367f032d93F642f64180aa3`
* **Purpose**: Binds DID strings (`did:key`, `did:web`) to credential/document hashes.
* **Access Control**: Identity owner controls updates (`onlyDIDOwner` modifier). Unauthorized actors cannot overwrite or rebind another organization's or holder's DID.
* **Reentrancy**: Protected by OpenZeppelin `ReentrancyGuard`.

### 2. `RevocationRegistry.sol`
* **Address**: `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`
* **Purpose**: Anchors W3C Bitstring Status List root digests (`anchorStatusList`) and individual credential revocations (`revokeCredential`).
* **Idempotency**: Prevents duplicate revocations with reverts (`"RevocationRegistry: Zaten iptal edilmis"`). Application bridge checks `isCredentialRevoked` before submitting to avoid redundant gas costs.

### 3. `EmergencyRecovery.sol`
* **Address**: `0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0`
* **Purpose**: Multi-sig social recovery (2-of-3 guardian consensus) inspired by EIP-4337, and AI-triggered emergency account quarantine.
* **AI Security Policy**: When fraud risk exceeds critical thresholds ($\ge 85$), `quarantineWallet(address, reason)` is triggered by the authorized system signer.
* **Authority Principle**: Blockchain does not calculate or override the AI risk score; it provides an immutable on-chain lock that prevents compromised wallets from signing transactions across the ecosystem.

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
        ▼                   ▼
     [FAILED] ◄──────── [FAILED]
```

* **`PENDING`**: Request generated, canonical hash computed, ready for RPC transmission.
* **`SUBMITTED`**: Transaction signed and broadcast to the mempool; transaction hash recorded.
* **`CONFIRMED`**: Transaction included in a block; receipt verified with `status == 1`. Block number and confirmation timestamp stored.
* **`FAILED`**: RPC node unreachable, timeout exceeded, or transaction reverted. Detailed `error_message` stored with retry counters.

---

## 5. Environment Configuration

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `BLOCKCHAIN_RPC_URL` | `http://127.0.0.1:8545` | JSON-RPC provider endpoint |
| `BLOCKCHAIN_CHAIN_ID` | `1337` | Local Hardhat chain ID (`11155111` for Sepolia) |
| `BLOCKCHAIN_PRIVATE_KEY` | Hardhat #0 Test Key | Transaction signer private key |
| `DID_REGISTRY_ADDRESS` | `0x5FbDB2315678afecb367f032d93F642f64180aa3` | Deployed `DIDRegistry.sol` |
| `REVOCATION_REGISTRY_ADDRESS`| `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512` | Deployed `RevocationRegistry.sol` |
| `EMERGENCY_RECOVERY_ADDRESS` | `0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0` | Deployed `EmergencyRecovery.sol` |
| `AUDIT_LOGGER_ADDRESS` | `0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9` | Deployed `AuditLogger.sol` |
| `BLOCKCHAIN_TIMEOUT_SECONDS` | `8.0` | Transaction receipt timeout before fail-open |
| `BLOCKCHAIN_ENABLED` | `true` | Master switch for blockchain bridge |

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
