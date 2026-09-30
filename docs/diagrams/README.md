# Secure SSI Platform - Architecture & Protocol Diagram Package

**Project**: Academic Secure SSI Platform (Graduation Thesis Reference Implementation)  
**Standard**: W3C VC DM v2.0, OpenID4VCI (Draft 13), OpenID4VP (Draft 20), EIP-4337, RFC 8785 (JCS)  
**Format**: Version-controlled, reproducible Mermaid diagrams  
**Scope**: Sprint 24 Final System Documentation  

---

## Table of Contents
- [D01 — High-Level System Architecture](#d01--high-level-system-architecture)
- [D02 — Stakeholder Role Ecosystem](#d02--stakeholder-role-ecosystem)
- [D03 — Holder Credential Lifecycle](#d03--holder-credential-lifecycle)
- [D04 — OID4VCI Credential Issuance Protocol](#d04--oid4vci-credential-issuance-protocol)
- [D05 — OID4VP Verifiable Presentation Protocol](#d05--oid4vp-verifiable-presentation-protocol)
- [D06 — 9-Point Verification Decision Matrix](#d06--9-point-verification-decision-matrix)
- [D07 — Consent & Data Minimization Flow](#d07--consent--data-minimization-flow)
- [D08 — Guardian Social Recovery (3-of-5 Shamir)](#d08--guardian-social-recovery-3-of-5-shamir)
- [D09 — AI Fraud Risk Scoring Pipeline](#d09--ai-fraud-risk-scoring-pipeline)
- [D10 — EVM Blockchain Integrity Anchoring](#d10--evm-blockchain-integrity-anchoring)
- [D11 — Security Boundaries & STRIDE Threat Model](#d11--security-boundaries--stride-threat-model)
- [D12 — Deployment & Runtime Process Architecture](#d12--deployment--runtime-process-architecture)
- [D13 — Conceptual Persistence & Data Model](#d13--conceptual-persistence--data-model)

---

## D01 — High-Level System Architecture

```mermaid
graph TB
    subgraph Client_Layer ["Layer 0: Presentation & Client Cockpit (React 18 + Vite 6)"]
        UI_Holder["Holder Wallet App<br/>(/wallet)"]
        UI_Issuer["Issuer Portal<br/>(/issuer)"]
        UI_Verifier["Verifier Portal<br/>(/verifier)"]
        UI_Guardian["Guardian Recovery Portal<br/>(/guardian)"]
        UI_Admin["Admin Operations Cockpit<br/>(/admin)"]
    end

    subgraph Gateway_Layer ["Layer 1: Security & API Gateway (:8000)"]
        GW["API Gateway Facade<br/>(FastAPI Reverse-Proxy)"]
        GW_Sec["Defensive Middleware:<br/>- Security Headers<br/>- Sliding Rate Limiting<br/>- Correlation ID (Tracing)"]
    end

    subgraph Core_Services ["Layer 2: Decentralized SSI Microservices"]
        ID_SVC["Identity & SSI Core (:8001)<br/>- W3C VC 2.0 / eddsa-jcs-2022<br/>- OID4VCI / OID4VP Protocols<br/>- DID Resolution (did:key, did:web)<br/>- Bitstring Status List v1.0"]
        FRAUD_SVC["AI Fraud Engine (:8002)<br/>- Hybrid XGBoost + Autoencoder<br/>- Behavioral Telemetry Scoring<br/>- Quarantine & Step-Up Auth"]
        REC_SVC["Guardian Recovery Service (:8003)<br/>- 3-of-5 Shamir Secret Sharing<br/>- 48h Time-Lock State Worker<br/>- Successor Key Rotation"]
    end

    subgraph Integrity_Layer ["Layer 3: Integrity, Ledger & Persistence"]
        EVM["EVM Blockchain (Hardhat :8545)<br/>- DIDRegistry.sol<br/>- RevocationRegistry.sol<br/>- EmergencyRecovery.sol<br/>- AuditLogger.sol"]
        MONGO[("Authoritative MongoDB<br/>- Wallets & DIDs<br/>- VCs & Bitstrings<br/>- Presentations & Challenges<br/>- Tamper-Proof Audit Outbox")]
    end

    UI_Holder -->|HTTPS / JSON| GW
    UI_Issuer -->|HTTPS / JSON| GW
    UI_Verifier -->|HTTPS / JSON| GW
    UI_Guardian -->|HTTPS / JSON| GW
    UI_Admin -->|HTTPS / JSON| GW

    GW --> GW_Sec
    GW_Sec -->|Internal Routing| ID_SVC
    GW_Sec -->|Internal Routing| FRAUD_SVC
    GW_Sec -->|Internal Routing| REC_SVC

    ID_SVC -->|Read / Write| MONGO
    REC_SVC -->|Read / Write| MONGO
    ID_SVC -.->|Async Telemetry| FRAUD_SVC
    ID_SVC -->|Canonical Digest Anchor| EVM
    REC_SVC -->|On-Chain Quorum Anchor| EVM
```

---

## D02 — Stakeholder Role Ecosystem

```mermaid
graph LR
    subgraph Stakeholders ["SSI Platform Multi-Stakeholder Ecosystem"]
        H["Holder<br/>(Citizen / Student / User)<br/>• Sovereign Key Custody<br/>• Selective Disclosure Consent<br/>• Presentation Generation"]
        I["Issuer<br/>(University / Authority)<br/>• Schema & Template Design<br/>• Credential Issuance<br/>• Status List Revocation"]
        V["Verifier<br/>(Employer / Service)<br/>• Presentation Request Creation<br/>• 9-Point Trust Verification<br/>• Verification Audit Logs"]
        G["Guardian<br/>(Trusted Contact / Institution)<br/>• Shamir Share Custody<br/>• Recovery Petition Review<br/>• Quorum Signing (3-of-5)"]
        A["Platform Admin<br/>(System Operator)<br/>• Node & Service Health<br/>• Smart Contract Anchors<br/>• Tamper-Evident Audit Trail"]
    end

    I -->|1. Issues W3C Credential (OID4VCI)| H
    V -->|2. Presentation Request (OID4VP)| H
    H -->|3. Verifiable Presentation (JCS Proof)| V
    V -->|4. Status Verification Query| I
    H -.->|5. Emergency Recovery Petition| G
    G -.->|6. Threshold Quorum Approval| H
    A -.->|7. Observability & Anchoring Audit| Stakeholders
```

---

## D03 — Holder Credential Lifecycle

```mermaid
stateDiagram-v2
    [*] --> OfferReceived: OID4VCI Credential Offer (/wallet/scan)
    OfferReceived --> Rejected: Holder Declines Offer
    OfferReceived --> Claimed: Holder Consents & Claims Credential
    
    Claimed --> StoredInWallet: Cryptographic Verification & Local Storage (/wallet)
    
    state StoredInWallet {
        [*] --> ActiveStatus
        ActiveStatus --> StatusPolled: Bitstring Status List v1.0 Query
        StatusPolled --> ActiveStatus: Bit = 0 (Valid)
        StatusPolled --> RevokedStatus: Bit = 1 (Revoked by Issuer)
        ActiveStatus --> SuspendedStatus: Temporary Suspension
        SuspendedStatus --> ActiveStatus: Suspension Lifted
    }

    StoredInWallet --> PresentationConsent: Verifier OID4VP Request Received
    PresentationConsent --> PresentationGenerated: Selective Disclosure Approved
    PresentationConsent --> PresentationAborted: Holder Rejects Request
    PresentationGenerated --> StoredInWallet: Nonce Consumed & Logged

    StoredInWallet --> Deleted: Local Purge by Holder
    RevokedStatus --> Deleted
    Rejected --> [*]
    Deleted --> [*]
```

---

## D04 — OID4VCI Credential Issuance Protocol

```mermaid
sequenceDiagram
    autonumber
    actor Holder as Holder Wallet
    participant Gateway as API Gateway (:8000)
    participant Issuer as Identity / Issuer Service (:8001)
    participant Mongo as MongoDB Storage
    participant Chain as EVM Smart Contracts

    Note over Holder,Issuer: Phase 1: Credential Offer Creation
    Issuer->>Issuer: Organization prepares credential payload
    Issuer->>Mongo: Persist credential offer & nonce
    Issuer-->>Holder: Deliver OID4VCI Offer URI / QR Code

    Note over Holder,Issuer: Phase 2: Authorization & Token Request
    Holder->>Gateway: POST /api/v1/oid4vci/token (Pre-authorized Code)
    Gateway->>Issuer: Forward token request
    Issuer->>Issuer: Verify pre-authorized code & rate limits
    Issuer-->>Holder: Access Token & Issuer Metadata

    Note over Holder,Issuer: Phase 3: Credential Request & Signing
    Holder->>Gateway: POST /api/v1/oid4vci/credential (Proof of Key Possession)
    Gateway->>Issuer: Forward credential request
    Issuer->>Issuer: Verify Holder DID & Ed25519 proof of possession
    Issuer->>Issuer: Canonicalize VC DM v2.0 payload via RFC 8785 JCS
    Issuer->>Issuer: Sign DataIntegrityProof (eddsa-jcs-2022)
    Issuer->>Mongo: Atomically bind to Bitstring Status List v1.0
    Issuer->>Chain: (Optional) Anchor Status List Root Hash
    Issuer->>Mongo: Write Audit Event to durable outbox
    Issuer-->>Holder: 200 OK (Signed Verifiable Credential JSON)
    Holder->>Holder: Verify signature & store in local wallet
```

---

## D05 — OID4VP Verifiable Presentation Protocol

```mermaid
sequenceDiagram
    autonumber
    actor Verifier as Verifier Console
    actor Holder as Holder Wallet
    participant Gateway as API Gateway (:8000)
    participant SSI as Identity Service (:8001)
    participant AI as AI Fraud Service (:8002)
    participant Chain as EVM Smart Contracts

    Note over Verifier,Holder: Phase 1: Presentation Request Creation
    Verifier->>Gateway: POST /api/v1/oid4vp/request
    Gateway->>SSI: Generate cryptographic challenge nonce
    SSI->>SSI: Bind challenge to verifier origin & expiry (300s)
    SSI-->>Verifier: Presentation Request (QR Code & deep link)

    Note over Verifier,Holder: Phase 2: Holder Review & Selective Disclosure
    Verifier->>Holder: Transmit request (QR scan or link)
    Holder->>Holder: Parse requested claims & verify verifier identity
    Holder->>Holder: User selects claims & grants explicit consent
    Holder->>Holder: Assemble Verifiable Presentation with server nonce
    Holder->>Holder: Sign VP DataIntegrityProof with holder Ed25519 key

    Note over Holder,Verifier: Phase 3: Presentation Submission & 9-Point Verification
    Holder->>Gateway: POST /api/v1/oid4vp/response
    Gateway->>SSI: Forward signed VP & challenge
    SSI->>SSI: 1. Cryptographic signature check (Ed25519)
    SSI->>SSI: 2. Issuer trust registry check
    SSI->>SSI: 3. Holder binding validation
    SSI->>SSI: 4. Expiration date check
    SSI->>SSI: 5. Bitstring Status List check (Revocation bit)
    SSI->>SSI: 6. Challenge nonce consumption (Anti-replay)
    
    Note over SSI,AI: Phase 4: Risk Scoring & Decision
    SSI->>AI: Evaluate transaction telemetry (IP, location, device, frequency)
    AI-->>SSI: Risk Score (0.00-1.00), Tier (LOW/MEDIUM/HIGH/CRITICAL)
    SSI->>SSI: Apply verification policy (Pass / Step-Up / Fail)
    SSI->>Chain: Anchor presentation verification digest
    SSI-->>Verifier: Verification Verdict (Claims, Proof Evidence, AI Risk Card)
```

---

## D06 — 9-Point Verification Decision Matrix

```mermaid
flowchart TD
    Start(["Incoming Verifiable Presentation Submission"]) --> C1{"Check 1: Signature Valid?<br/>(DataIntegrityProof / eddsa-jcs-2022)"}
    
    C1 -- No --> F1["FAIL: INVALID_SIGNATURE (HTTP 400)"]
    C1 -- Yes --> C2{"Check 2: Issuer Trusted?<br/>(did:web / did:key Trust Registry)"}
    
    C2 -- No --> F2["FAIL: UNTRUSTED_ISSUER (HTTP 400)"]
    C2 -- Yes --> C3{"Check 3: Holder Bound?<br/>(VP Holder DID matches VC Subject DID)"}
    
    C3 -- No --> F3["FAIL: HOLDER_BINDING_MISMATCH (HTTP 400)"]
    C3 -- Yes --> C4{"Check 4: Temporal Validity?<br/>(nbf <= now < exp)"}
    
    C4 -- No --> F4["FAIL: CREDENTIAL_EXPIRED (HTTP 400)"]
    C4 -- Yes --> C5{"Check 5: Revocation Clear?<br/>(Bitstring Status List index == 0)"}
    
    C5 -- Revoked --> F5["FAIL: CREDENTIAL_REVOKED (HTTP 400)"]
    C5 -- Clear --> C6{"Check 6: Challenge Valid?<br/>(One-time nonce match & unconsumed)"}
    
    C6 -- No / Replay --> F6["FAIL: REPLAY_CHALLENGE_EXPIRED (HTTP 400)"]
    C6 -- Valid --> C7{"Check 7: AI Risk Assessment<br/>(Telemetry anomaly scoring)"}
    
    C7 -- Risk > 0.85 (Critical) --> F7["QUARANTINE / STEP-UP: HIGH_FRAUD_RISK"]
    C7 -- Risk <= 0.85 --> C8["Check 8: Blockchain Integrity Anchor<br/>(EVM transaction digest recorded)"]
    
    C8 --> C9["Check 9: Final Policy Decision<br/>(All criteria satisfied)"]
    C9 --> Pass(["VERIFIED SUCCESS: Claims Disclosed & Audited"])

    style Start fill:#1e293b,stroke:#3b82f6,color:#fff
    style Pass fill:#064e3b,stroke:#10b981,color:#fff
    style F1 fill:#450a0a,stroke:#ef4444,color:#fff
    style F2 fill:#450a0a,stroke:#ef4444,color:#fff
    style F3 fill:#450a0a,stroke:#ef4444,color:#fff
    style F4 fill:#450a0a,stroke:#ef4444,color:#fff
    style F5 fill:#450a0a,stroke:#ef4444,color:#fff
    style F6 fill:#450a0a,stroke:#ef4444,color:#fff
    style F7 fill:#78350f,stroke:#f59e0b,color:#fff
```

---

## D07 — Consent & Data Minimization Flow

```mermaid
graph TD
    subgraph Verifier_Spec ["Verifier Requirements Definition"]
        VR["Verification Request<br/>• Required Claims: [FullName, DegreeType]<br/>• Optional Claims: [GPA, GraduationDate]<br/>• Purpose: Academic Accreditation Review<br/>• Data Retention: 30 Days"]
    end

    subgraph Holder_Cockpit ["Holder Presentation Consent UI (/wallet/consent)"]
        UI_Review["Claims Transparency Panel<br/>• Displays requesting verifier identity<br/>• Explains declared purpose & retention"]
        UI_Toggle["Data Minimization Selectors<br/>[x] FullName (Mandatory)<br/>[x] DegreeType (Mandatory)<br/>[ ] GPA (Omitted by Holder)<br/>[ ] GraduationDate (Omitted by Holder)"]
        UI_Action{"Holder Decision"}
    end

    subgraph Result_Action ["Cryptographic Outcome"]
        Approved["Generate Minimized Presentation<br/>• Includes ONLY selected claims<br/>• Excludes omitted attributes<br/>• Holder binds signature to current nonce"]
        Declined["Abort Request<br/>• Zero claims transmitted<br/>• Verifier notified of user cancellation"]
    end

    VR --> UI_Review
    UI_Review --> UI_Toggle
    UI_Toggle --> UI_Action
    UI_Action -- "Approve & Sign" --> Approved
    UI_Action -- "Reject Request" --> Declined
```

---

## D08 — Guardian Social Recovery (3-of-5 Shamir)

```mermaid
sequenceDiagram
    autonumber
    actor Holder as Lost Wallet Holder
    participant Recovery as Recovery Service (:8003)
    actor G1 as Guardian #1
    actor G2 as Guardian #2
    actor G3 as Guardian #3
    participant Mongo as MongoDB Storage
    participant Identity as Identity Service (:8001)
    participant Chain as EmergencyRecovery.sol

    Note over Holder,Recovery: Phase 1: Recovery Request Initiation
    Holder->>Recovery: POST /api/v1/recovery/requests (Subject DID, Successor Key Reference)
    Recovery->>Mongo: Create pending recovery petition (Status: PENDING_APPROVALS)
    Recovery->>Chain: Register recovery initiation on-chain

    Note over Recovery,G3: Phase 2: Guardian Quorum Authorization (Threshold: 3-of-5)
    G1->>Recovery: POST /api/v1/recovery/requests/{id}/decision (APPROVE + Encrypted Share 1)
    Recovery->>Mongo: Record Decision 1/3 (Idempotent)
    G2->>Recovery: POST /api/v1/recovery/requests/{id}/decision (APPROVE + Encrypted Share 2)
    Recovery->>Mongo: Record Decision 2/3 (Idempotent)
    G3->>Recovery: POST /api/v1/recovery/requests/{id}/decision (APPROVE + Encrypted Share 3)
    Recovery->>Mongo: Record Decision 3/3 (Threshold Reached)

    Note over Recovery,Mongo: Phase 3: Time-Lock Period (Anti-Hijacking Delay: 48h)
    Recovery->>Mongo: Update Status: TIMELOCK_ACTIVE (Unlock At: T + 48h)
    Note over Holder: Wallet Owner receives cancellation notice.<br/>Can cancel during time-lock if fraudulent.

    Note over Recovery,Identity: Phase 4: Time-Lock Expiry & Key Rotation
    Recovery->>Recovery: Time-Lock Worker detects expiry (now >= unlock_at)
    Recovery->>Identity: Orchestrate successor key rotation
    Identity->>Identity: Rebind wallet DID to new Ed25519 key reference
    Identity->>Chain: Submit ownership transfer to EmergencyRecovery.sol
    Recovery->>Mongo: Update Status: COMPLETED
    Recovery-->>Holder: Recovery Complete (New Wallet Key Activated)
```

---

## D09 — AI Fraud Risk Scoring Pipeline

```mermaid
flowchart LR
    subgraph Ingestion ["Telemetry Ingestion"]
        E1["IP Address & ASN"]
        E2["Geo-Coordinates"]
        E3["Device / User-Agent"]
        E4["Timestamp & Cadence"]
        E5["Failure Counts"]
    end

    subgraph Feature_Engineering ["Feature Extraction Engine"]
        F1["Impossible Travel Velocity (km/h)"]
        F2["Tor / Proxy / VPN Exit Detection"]
        F3["Rapid Brute-Force Rate"]
        F4["Out-of-Hours Presentation"]
        F5["Unusual User-Agent Entropy"]
    end

    subgraph Model_Inference ["Hybrid AI Inference Engine (:8002)"]
        XGB["XGBoost Classifier<br/>(Supervised Tabular Risk)<br/>Weight: 0.60"]
        AE["PyTorch Autoencoder<br/>(Unsupervised Anomaly Reconstruction)<br/>Weight: 0.40"]
        Score["Ensemble Risk Score Calculator<br/>Score = 0.60(XGB) + 0.40(AE_Loss)"]
    end

    subgraph Decision ["Risk Tier & Policy Action"]
        T1["LOW (0.00 - 0.30)<br/>Verdict: ALLOW"]
        T2["MEDIUM (0.31 - 0.60)<br/>Verdict: ALLOW with Audit Flag"]
        T3["HIGH (0.61 - 0.85)<br/>Verdict: STEP-UP MFA REQUIRED"]
        T4["CRITICAL (0.86 - 1.00)<br/>Verdict: AUTO-QUARANTINE"]
    end

    Ingestion --> Feature_Engineering
    Feature_Engineering --> XGB
    Feature_Engineering --> AE
    XGB --> Score
    AE --> Score
    Score --> Decision
```

---

## D10 — EVM Blockchain Integrity Anchoring

```mermaid
sequenceDiagram
    autonumber
    participant Service as SSI Core Microservice
    participant Outbox as Durable Mongo Outbox
    participant Web3 as Web3 JSON-RPC Adapter
    participant Hardhat as Hardhat EVM Node (:8545)
    participant Contract as Solidity Smart Contract

    Note over Service,Contract: Strict Rule: ZERO PII and ZERO Raw Credentials on Chain
    Service->>Service: Canonicalize event JSON (RFC 8785 JCS)
    Service->>Service: Compute SHA-256 Digest (32 bytes)
    Service->>Outbox: Persist canonical digest & status PENDING_ANCHOR
    
    Outbox->>Web3: Poll pending outbox items
    Web3->>Hardhat: eth_sendTransaction (Invoking smart contract method)
    
    alt Anchor Credential Status
        Hardhat->>Contract: RevocationRegistry.setBitstringRoot(issuerDid, rootHash)
    else Anchor DID Document
        Hardhat->>Contract: DIDRegistry.registerDID(did, docHash)
    else Anchor Audit Event
        Hardhat->>Contract: AuditLogger.logEvent(eventHash, category)
    else Anchor Recovery Action
        Hardhat->>Contract: EmergencyRecovery.executeRecovery(wallet, newKey)
    end

    Contract-->>Hardhat: Emit Transaction Receipt & Block Confirmation
    Hardhat-->>Web3: Transaction Hash (0x...) & Gas Used
    Web3->>Outbox: Update Mongo Record with on_chain_tx_hash & status CONFIRMED
```

---

## D11 — Security Boundaries & STRIDE Threat Model

```mermaid
graph TB
    subgraph Untrusted_Zone ["Untrusted External Zone"]
        Attacker["Potential Adversary<br/>• Network Sniffer<br/>• Man-in-the-Middle<br/>• Impersonator"]
    end

    subgraph Perimeter ["Network Boundary & Ingress Defense"]
        TLS["HTTPS / TLS 1.3 Encryption"]
        GW["API Gateway (:8000)<br/>• Rate Limiting (180 req/min)<br/>• Correlation ID Tracing<br/>• Strict CORS Allowlist"]
    end

    subgraph Service_Perimeter ["Authenticated Microservice Core"]
        Auth["Argon2id + Short-Lived HS256 JWT"]
        RBAC["Role-Based Access Control (HOLDER, ISSUER, VERIFIER, GUARDIAN, ADMIN)"]
        ObjAuth["Object-Level Ownership Validation"]
        InputSan["JSON Schema & Pydantic Input Sanitation"]
    end

    subgraph Cryptographic_Boundary ["Isolated Cryptographic Vault"]
        KMS["Provider-Neutral KMS Interface<br/>• Ed25519 Signing Keys<br/>• Opaque Key Handles<br/>• Private Keys NEVER Exported to Storage"]
    end

    subgraph Storage_Boundary ["Persistence & Immutability Boundary"]
        Mongo["MongoDB Collections<br/>• Encrypted Connection<br/>• Optimistic Version Locking<br/>• Audit Log Append-Only"]
        Chain["EVM Blockchain<br/>• Zero PII Integrity Proofs<br/>• Non-Repudiation Anchors"]
    end

    Attacker -->|Threat: Replay / DDoS| TLS
    TLS --> GW
    GW -->|Threat: Privilege Escalation| Auth
    Auth --> RBAC
    RBAC --> ObjAuth
    ObjAuth --> InputSan
    InputSan -->|Threat: Key Extraction| KMS
    InputSan -->|Threat: Data Tampering| Mongo
    InputSan -->|Threat: Repudiation| Chain
```

---

## D12 — Deployment & Runtime Process Architecture

```mermaid
graph LR
    subgraph Host ["Local Development Host (Windows / Linux)"]
        subgraph Frontend_Runtime ["Frontend Host (:5173)"]
            VITE["Vite Dev / Nginx Production Server<br/>Port: 5173<br/>App: apps/web"]
        end

        subgraph Gateway_Runtime ["Gateway Process (:8000)"]
            GW_PROC["uvicorn app.main:app<br/>Port: 8000<br/>Service: services/api-gateway"]
        end

        subgraph Microservice_Processes ["SSI Microservice Processes"]
            ID_PROC["Identity Service (:8001)<br/>uvicorn app.main:app<br/>services/identity-service"]
            FRAUD_PROC["Fraud Service (:8002)<br/>uvicorn app.main:app<br/>services/fraud-service"]
            REC_PROC["Recovery Service (:8003)<br/>uvicorn app.main:app<br/>services/recovery-service"]
        end

        subgraph Hardhat_Process ["Blockchain Node (:8545)"]
            HH_NODE["npx hardhat node<br/>Port: 8545<br/>Directory: blockchain/"]
        end

        subgraph Storage_Engine ["Database Engine (:27017)"]
            MONGO_SVC[("MongoDB Community Server<br/>Port: 27017<br/>Databases: ssi_identity, ssi_recovery")]
        end
    end

    VITE -->|HTTP/REST Proxy| GW_PROC
    GW_PROC -->|HTTP Proxy| ID_PROC
    GW_PROC -->|HTTP Proxy| FRAUD_PROC
    GW_PROC -->|HTTP Proxy| REC_PROC
    ID_PROC -->|PyMongo Client| MONGO_SVC
    REC_PROC -->|PyMongo Client| MONGO_SVC
    ID_PROC -->|Web3.py RPC| HH_NODE
    REC_PROC -->|Web3.py RPC| HH_NODE
```

---

## D13 — Conceptual Persistence & Data Model

```mermaid
erDiagram
    USERS ||--o{ WALLETS : owns
    USERS ||--o{ AUDIT_EVENTS : triggers
    WALLETS ||--o{ MANAGED_KEYS : holds
    WALLETS ||--o{ CREDENTIALS : stores
    WALLETS ||--o{ PRESENTATIONS : generates
    
    CREDENTIALS ||--|| CREDENTIAL_STATUS : references
    CREDENTIALS }o--|| STATUS_LIST_ENTRIES : indexed_in
    
    PRESENTATIONS ||--|| PRESENTATION_CHALLENGES : consumes
    PRESENTATIONS ||--o{ FRAUD_EVENTS : evaluated_by
    
    WALLETS ||--o{ RECOVERY_REQUESTS : target_of
    RECOVERY_REQUESTS ||--|{ GUARDIAN_DECISIONS : requires
    
    AUDIT_EVENTS ||--o| BLOCKCHAIN_ANCHORS : anchored_by

    USERS {
        string id PK
        string username UK
        string password_hash
        string role
        string status
        date created_at
    }

    WALLETS {
        string id PK
        string owner_id FK
        string active_did UK
        string status
        int version
    }

    MANAGED_KEYS {
        string id PK
        string wallet_id FK
        string provider_reference
        string algorithm
        string public_key_jwk
        string status
    }

    CREDENTIALS {
        string id PK
        string wallet_id FK
        string issuer_did
        string subject_did
        string credential_type
        json raw_vc_json
        string status
        date issuance_date
        date expiration_date
    }

    CREDENTIAL_STATUS {
        string credential_id PK
        string status_list_id FK
        int status_list_index
        string revocation_status
        date last_updated
    }

    PRESENTATIONS {
        string id PK
        string wallet_id FK
        string verifier_did
        string challenge_id FK
        json raw_vp_json
        string verification_status
        float ai_risk_score
    }

    PRESENTATION_CHALLENGES {
        string id PK
        string nonce UK
        string verifier_origin
        date expires_at
        boolean consumed
    }

    RECOVERY_REQUESTS {
        string id PK
        string wallet_id FK
        string successor_key_ref
        int quorum_required
        int approvals_count
        string status
        date timelock_until
    }

    GUARDIAN_DECISIONS {
        string id PK
        string recovery_request_id FK
        string guardian_did
        string decision
        string encrypted_share_blob
    }

    FRAUD_EVENTS {
        string id PK
        string presentation_id FK
        string ip_address
        float risk_score
        string risk_tier
        json feature_vector
    }

    BLOCKCHAIN_ANCHORS {
        string id PK
        string event_id FK
        string canonical_hash UK
        string tx_hash
        int block_number
        string contract_address
        string status
    }
```
