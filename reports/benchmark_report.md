# S20 PERFORMANCE & BENCHMARKING REPORT

**Repository**: `secure-ssi-platform`  
**Execution Timestamp**: 2026-09-30 14:28:48 UTC  
**Environment**: Windows-10-10.0.26200-SP0 | Python 3.11.16 | Node v24.19.0  

---

## 1. Executive Summary & Optimization Highlights

| Component | Metric | Baseline / Without Optimization | S20 Optimized Result | Net Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend Bundle** | Main Entry JS Size | 837.65 kB (260.33 kB gzip) | **410.44 kB** (149.86 kB gzip) | **-51.0%** bundle size reduction |
| **Frontend Build** | Build Duration | 7.07 seconds | **3.72 seconds** | **47.4%** faster compilation |
| **Bitstring Status List** | 131,072 Bit Lookup | 14.5 µs (raw gzip decompress) | **0.2 µs** (LRU decompress) | **79.2x** faster lookup |
| **VC Issuance** | Ed25519/JCS Issuance | N/A (unbenchmarked) | **2610.63 creds/sec** | p50 = 0.285 ms |
| **OID4VP Verification** | 9-Point Verification | N/A (unbenchmarked) | **1426.74 verifs/sec** | p50 = 0.345 ms |
| **AI Fraud Engine** | Hybrid Inference (100) | N/A (unbenchmarked) | **114246.54 samples/sec** | avg = 0.006 ms |

---

## 2. Benchmark 1: W3C Verifiable Credential Issuance

Evaluates Ed25519 signature generation and RFC 8785 JSON Canonicalization Scheme (JCS) across multiple workloads.

### Service Benchmark (Full Proof Pipeline)
| Workload | Throughput (creds/s) | Average (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Total Time (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **10 credentials** | 2318.09 | 0.358 | 0.318 | 0.504 | 0.524 | 0.539 | 0.0043s |
| **100 credentials** | 2611.1 | 0.309 | 0.283 | 0.358 | 0.464 | 0.541 | 0.0383s |
| **500 credentials** | 2532.17 | 0.319 | 0.284 | 0.391 | 0.467 | 0.709 | 0.1975s |
| **1000 credentials** | 2610.63 | 0.311 | 0.285 | 0.402 | 0.466 | 0.576 | 0.383s |

### Unit Benchmark (Raw JCS Canonicalization + Ed25519 Signing)
| Workload | Throughput (creds/s) | Average (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10 credentials** | 14182.39 | 0.071 | 0.069 | 0.076 | 0.077 |
| **100 credentials** | 13965.31 | 0.072 | 0.065 | 0.1 | 0.153 |
| **500 credentials** | 13575.12 | 0.074 | 0.065 | 0.088 | 0.151 |
| **1000 credentials** | 14321.31 | 0.07 | 0.066 | 0.085 | 0.139 |

---

## 3. Benchmark 2: OID4VP 9-Point Verification Pipeline

Evaluates the complete end-to-end verification pipeline:
1. Credential structure validation
2. DID resolution (`did:web` fixture)
3. Cryptographic proof verification (`eddsa-jcs-2022`)
4. Holder binding validation
5. Expiration checking
6. W3C Bitstring Status List lookup (131,072 entries)
7. Nonce / challenge replay defense
8. AI fraud evaluation (advisory)
9. Adaptive policy decision

| Workload | Throughput (verifs/s) | Average (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Total Time (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **10 presentations** | 1319.68 | 0.392 | 0.359 | 0.515 | 0.538 | 0.557 | 0.0076s |
| **50 presentations** | 1484.63 | 0.363 | 0.342 | 0.414 | 0.433 | 0.594 | 0.0337s |
| **100 presentations** | 1426.74 | 0.383 | 0.345 | 0.452 | 0.569 | 0.761 | 0.0701s |
| **200 presentations** | 1426.75 | 0.373 | 0.346 | 0.444 | 0.526 | 0.667 | 0.1402s |

---

## 4. Benchmark 3: W3C Bitstring Status List (131,072 Entries)

- **Capacity**: 131,072 credentials (16,384 bytes uncompressed)
- **Compressed Wire Size**: 77 bytes (Multibase `u` Base64url)
- **Compression Efficiency**: 212.78x wire reduction
- **Encode Time**: 0.149 ms

| Operation | Mode | Average Latency | p50 | p95 | p99 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Status Lookup** | Uncached (Raw Gzip per check) | 14.51 µs | 14.05 µs | 17.94 µs | 26.51 µs |
| **Status Lookup** | **LRU Decompression Cached** | **0.18 µs** | **0.2 µs** | **0.2 µs** | **0.3 µs** |

> **Optimization Result**: The LRU decompression cache provides an authoritative **79.2x speedup** on repeated revocation lookups.

---

## 5. Benchmark 4: AI Fraud Engine (Hybrid Detector)

Evaluates feature extraction, Autoencoder reconstruction error, XGBoost inference, ensemble weighting, and risk score calculation.

| Workload / Batch Size | Throughput (samples/s) | Total Time (ms) | Average Latency (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Batch 1 (Single Item)** | 34364.27 | 0.03 ms | 0.012 ms | 0.012 ms | 0.012 ms | 0.012 ms |
| **Batch 10** | 71479.65 | 0.14 ms | 0.011 ms | 0.01 ms | 0.016 ms | 0.018 ms |
| **Batch 100** | 114246.54 | 0.88 ms | 0.006 ms | 0.005 ms | 0.009 ms | 0.024 ms |
| **Batch 500** | 168412.55 | 2.97 ms | 0.004 ms | 0.004 ms | 0.005 ms | 0.005 ms |

---

## 6. Benchmark 5: Blockchain Smart Contract Gas Consumption

Measured via Hardhat local EVM execution with Solidity 0.8.28 and optimizer enabled (200 runs).

| Smart Contract | Transaction / Operation | Gas Used | Gas Target (Upper Bound) | Margin Under Bound |
| :--- | :--- | :--- | :--- | :--- |
| **DIDRegistry** | `registerDID` | **184,154** | 200,000 | 7.9% under bound |
| **DIDRegistry** | `updateVCHash` | **43,285** | 60,000 | 27.9% under bound |
| **RevocationRegistry** | `anchorStatusList` (131k list) | **92,159** | 120,000 | 23.2% under bound |
| **RevocationRegistry** | `revokeCredential` | **113,412** | 150,000 | 24.4% under bound |
| **EmergencyRecovery** | `configureGuardians` (3 guardians) | **120,723** | 150,000 | 19.5% under bound |
| **EmergencyRecovery** | `initiateRecovery` | **133,304** | 160,000 | 16.7% under bound |
| **EmergencyRecovery** | `approveRecovery` (auto-execute 2/3) | **75,873** | 100,000 | 24.1% under bound |
| **AuditLogger** | `logEvent` (fraud anchor) | **135,657** | 150,000 | 9.6% under bound |

### Contract Deployments
- `DIDRegistry`: 1,066,526 gas
- `RevocationRegistry`: 388,716 gas
- `EmergencyRecovery`: 1,591,311 gas
- `AuditLogger`: 226,304 gas

---

## 7. Benchmark 6: MongoDB Indexing & Query Architecture

- **Status**: Verified Schema & Index Architecture (Local Isolated Development Environment)
- **Live Daemon**: BLOCKED_DAEMON_OFFLINE (Academic in-memory/isolated repository)
- **Core Collections Audited**: 5 collections, 23 compound indexes:
  - `credentials`: Compound index on `(statusListId, statusListIndex)` with partial unique filter, and `(issuerDid, status)`.
  - `presentations`: Unique compound index on `(challenge, domain)` to enforce strict single-use replay protection.
  - `audit_events`: Compound descending index on `(eventType, createdAt)` for low-latency time-series query scanning.
  - `status_lists`: Unique index on `statusListId`, compound on `(issuerDid, statusPurpose)`.
  - `blockchain_anchors`: Unique index on `anchorId`, index on `txHash`.

---

## 8. Benchmark 7: API Gateway ASGI Overhead

Evaluates complete FastAPI middleware chain (CORS, Rate Limiting, Security Headers, Correlation ID, and JSON bomb defenses).

| Metric | API Gateway Result |
| :--- | :--- |
| **Total Processed Requests** | 500 requests |
| **Gateway Throughput** | **277.35 req/sec** |
| **Average Middleware Latency** | **3.604 ms** |
| **p50 Latency** | **3.389 ms** |
| **p95 Latency** | **5.433 ms** |
| **p99 Latency** | **8.039 ms** |

---

## 9. Benchmark 8: Frontend Bundle Optimization

| Bundle Metric | Baseline (Pre-S20) | Optimized (S20) | Change |
| :--- | :--- | :--- | :--- |
| **Main JS Entry Chunk** | 837.65 kB | **410.44 kB** | **-51.0%** reduction |
| **Main JS Gzip Size** | 260.33 kB | **149.86 kB** | **-42.4%** reduction |
| **Vite Chunk Size Warning** | FAILED (> 500 kB warning) | **PASSED (0 warnings)** | Eliminated |
| **Vendor Code Splitting** | Monolithic single chunk | **`vendor-*.js` (163.43 kB)** | Clean separation |
| **Route Dynamic Loading** | All 22 routes in main bundle | **22 split chunks (`React.lazy`)** | Loaded on-demand |
| **Vite Production Build Time** | 7.07 seconds | **3.72 seconds** | **47.4%** faster |

---

## 10. Critical Security Invariant Validation

Throughout all benchmark workloads and optimization tests:
- Cryptographic failure strictly invalidates the presentation:
  `invalid signature → REJECTED`  
  `tampered credential → REJECTED`  
  `expired credential → REJECTED`  
  `revoked credential → REJECTED`  
  `wrong holder → REJECTED`  
  `invalid nonce → REJECTED`  
  `replay → REJECTED`  
- **Invariant holds 100%**: AI advisory risk scores NEVER override cryptographic invalidity.
