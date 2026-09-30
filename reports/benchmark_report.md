# S20 PERFORMANCE & BENCHMARKING REPORT

**Repository**: `secure-ssi-platform`  
**Execution Timestamp**: 2026-09-30 14:13:43 UTC  
**Environment**: Windows-10-10.0.26200-SP0 | Python 3.11.16 | Node v24.19.0  

---

## 1. Executive Summary & Optimization Highlights

| Component | Metric | Baseline / Without Optimization | S20 Optimized Result | Net Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend Bundle** | Main Entry JS Size | 837.65 kB (260.33 kB gzip) | **410.44 kB** (149.86 kB gzip) | **-51.0%** bundle size reduction |
| **Frontend Build** | Build Duration | 7.07 seconds | **3.72 seconds** | **47.4%** faster compilation |
| **Bitstring Status List** | 131,072 Bit Lookup | 15.9 µs (raw gzip decompress) | **0.2 µs** (LRU decompress) | **85.2x** faster lookup |
| **VC Issuance** | Ed25519/JCS Issuance | N/A (unbenchmarked) | **2677.76 creds/sec** | p50 = 0.278 ms |
| **OID4VP Verification** | 9-Point Verification | N/A (unbenchmarked) | **1469.41 verifs/sec** | p50 = 0.336 ms |
| **AI Fraud Engine** | Hybrid Inference (100) | N/A (unbenchmarked) | **168208.57 samples/sec** | avg = 0.004 ms |

---

## 2. Benchmark 1: W3C Verifiable Credential Issuance

Evaluates Ed25519 signature generation and RFC 8785 JSON Canonicalization Scheme (JCS) across multiple workloads.

### Service Benchmark (Full Proof Pipeline)
| Workload | Throughput (creds/s) | Average (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Total Time (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **10 credentials** | 2608.58 | 0.314 | 0.298 | 0.36 | 0.411 | 0.451 | 0.0038s |
| **100 credentials** | 2648.85 | 0.308 | 0.274 | 0.411 | 0.537 | 0.594 | 0.0378s |
| **500 credentials** | 2648.07 | 0.307 | 0.279 | 0.4 | 0.469 | 0.57 | 0.1888s |
| **1000 credentials** | 2677.76 | 0.304 | 0.278 | 0.381 | 0.447 | 0.558 | 0.3734s |

### Unit Benchmark (Raw JCS Canonicalization + Ed25519 Signing)
| Workload | Throughput (creds/s) | Average (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10 credentials** | 14914.24 | 0.067 | 0.065 | 0.077 | 0.077 |
| **100 credentials** | 14853.32 | 0.067 | 0.064 | 0.077 | 0.134 |
| **500 credentials** | 14516.44 | 0.069 | 0.064 | 0.091 | 0.147 |
| **1000 credentials** | 14805.19 | 0.068 | 0.063 | 0.084 | 0.139 |

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
| **10 presentations** | 1283.12 | 0.436 | 0.408 | 0.571 | 0.585 | 0.596 | 0.0078s |
| **50 presentations** | 1454.07 | 0.371 | 0.341 | 0.465 | 0.543 | 0.6 | 0.0344s |
| **100 presentations** | 1469.41 | 0.369 | 0.336 | 0.486 | 0.56 | 0.622 | 0.0681s |
| **200 presentations** | 1488.13 | 0.362 | 0.339 | 0.434 | 0.511 | 0.591 | 0.1344s |

---

## 4. Benchmark 3: W3C Bitstring Status List (131,072 Entries)

- **Capacity**: 131,072 credentials (16,384 bytes uncompressed)
- **Compressed Wire Size**: 77 bytes (Multibase `u` Base64url)
- **Compression Efficiency**: 212.78x wire reduction
- **Encode Time**: 0.284 ms

| Operation | Mode | Average Latency | p50 | p95 | p99 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Status Lookup** | Uncached (Raw Gzip per check) | 15.9 µs | 13.3 µs | 31.93 µs | 49.5 µs |
| **Status Lookup** | **LRU Decompression Cached** | **0.19 µs** | **0.2 µs** | **0.2 µs** | **0.3 µs** |

> **Optimization Result**: The LRU decompression cache provides an authoritative **85.2x speedup** on repeated revocation lookups.

---

## 5. Benchmark 4: AI Fraud Engine (Hybrid Detector)

Evaluates feature extraction, Autoencoder reconstruction error, XGBoost inference, ensemble weighting, and risk score calculation.

| Workload / Batch Size | Throughput (samples/s) | Total Time (ms) | Average Latency (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Batch 1 (Single Item)** | 33783.79 | 0.03 ms | 0.013 ms | 0.013 ms | 0.013 ms | 0.013 ms |
| **Batch 10** | 70771.42 | 0.14 ms | 0.011 ms | 0.01 ms | 0.016 ms | 0.018 ms |
| **Batch 100** | 168208.57 | 0.59 ms | 0.004 ms | 0.004 ms | 0.005 ms | 0.006 ms |
| **Batch 500** | 156568.03 | 3.19 ms | 0.005 ms | 0.004 ms | 0.006 ms | 0.007 ms |

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
| **Gateway Throughput** | **262.35 req/sec** |
| **Average Middleware Latency** | **3.81 ms** |
| **p50 Latency** | **3.726 ms** |
| **p95 Latency** | **4.844 ms** |
| **p99 Latency** | **5.306 ms** |

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
