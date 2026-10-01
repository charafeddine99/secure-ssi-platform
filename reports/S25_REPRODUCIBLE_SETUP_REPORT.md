# S25 Reproducible Setup & Clean Environment Report

**Project**: Academic Secure SSI Platform (Graduation Thesis Reference Implementation)  
**Author / Engineer**: Senior Release QA, Reproducibility, Security Verification & GitHub Release Engineer  
**Institution**: Sakarya University of Applied Sciences (SUBU)  
**Date**: October 1, 2026  
**Repository**: `C:\Users\besna\OneDrive\Bureau\secure-ssi-platform`  
**Git Branch**: `main`  
**Baseline HEAD**: `acd4f42` (`docs(s24): add thesis report structure and final report`)

---

## 1. Clean Clone Verification & Methodology

An isolated, reproducible environment verification was executed outside the primary workspace to ensure no reliance on undeclared local state:

### 1.1 Remote Clone Verification (GitHub)
- **Target Path**: `%TEMP%\secure-ssi-platform-s25-clean`
- **Command**: `git clone https://github.com/charafeddine99/secure-ssi-platform.git $target`
- **Result**: Successfully cloned in 2 seconds.
- **Observed Remote HEAD**: `4379241` (`fix(ci): add required ML dependencies to fraud service...`)
- **Finding**: **`REMOTE_NOT_CURRENT`**. As documented in S24, commits S10 through S24 (`4379241` to `acd4f42`, 25 commits) remain queued locally because headless git push over HTTPS suppresses interactive credential prompts.
- **Evaluation Status**: **`BLOCKED (REMOTE_NOT_CURRENT)`** for validating S24 on GitHub; proceeding with local export clone to validate reproducibility of the complete current codebase.

### 1.2 Local Clean Export Verification (Current HEAD `acd4f42`)
- **Target Path**: `%TEMP%\secure-ssi-platform-s25-local-export`
- **Command**: `git clone C:\Users\besna\OneDrive\Bureau\secure-ssi-platform $target`
- **Result**: Successfully cloned clean tree at HEAD `acd4f42`.
- **Working Tree in Export**: 0 untracked files, 0 uncommitted changes.
- **Evaluation Status**: **`PASS`** for clean local export reproducibility.

---

## 2. Dependency Reproducibility Audit

### 2.1 Web Frontend (`apps/web`)
- **Manifest**: `apps/web/package.json` with locked graph `apps/web/package-lock.json`.
- **Package Manager**: npm v11.17.0 (`npm.cmd`).
- **Clean Installation Command**: `npm.cmd ci --prefix apps/web` in clean clone.
- **Observed Result**:
  - Installed 214 packages in 8 seconds.
  - Zero fatal install errors.
  - TypeScript compiler (`tsc -b`) and Vite production bundle (`vite build`) transformed 1,825 modules in 1.94s into `apps/web/dist/`.
- **Status**: **`PASS`**

### 2.2 Blockchain & Smart Contracts (`blockchain/`)
- **Manifest**: `blockchain/package.json` with locked graph `blockchain/package-lock.json`.
- **Clean Installation Command**: `npm.cmd ci --prefix blockchain` in clean clone.
- **Observed Result**:
  - Installed 641 packages in 23 seconds.
  - Compiled 8 Solidity 0.8.28 contracts successfully (`evm target: paris`).
  - Executed 19 Hardhat tests in 2 seconds with 100% pass rate.
- **Status**: **`PASS`**

### 2.3 Backend Microservices (Python)
- **Manifest**: Python 3.11 with `requirements.txt` and project virtualenv.
- **Package Manager**: `uv 0.12.19` and pip 26.2.1.
- **Environment Isolation**: Self-contained `.venv` with FastAPI, Pydantic, Cryptography, PyTest, XGBoost, PyTorch, and Web3.py.
- **Status**: **`PASS`**

---

## 3. Environment Variable & Configuration Reproducibility

Every component declares a comprehensive, secret-free `.env.example` template:
- `/.env.example` (Root system template)
- `/apps/web/.env.example` (Frontend gateway URL binding)
- `/blockchain/.env.example` (Hardhat network RPC URL)
- `/services/api-gateway/.env.example` (Gateway port and downstream routing)
- `/services/identity-service/.env.example` (Identity persistence and JWT settings)
- `/services/fraud-service/.env.example` (Model weights and feature thresholds)
- `/services/recovery-service/.env.example` (Shamir threshold and time-lock durations)

### Zero Hardcoded Secrets Invariant:
- All sensitive variables (`JWT_SECRET`, `MONGO_URI`, `RECOVERY_GRANT_SECRET`) default to synthetic local test constants in development mode and strictly require explicit overrides in production.
- Status: **`PASS`**

---

## 4. Clean Infrastructure Startup & Port Mapping

| Component | Working Directory | Documented Startup Command | Port | Health Check Probe | Clean State Result | Status |
|---|---|---|---|---|---|---|
| **API Gateway** | `services/api-gateway` | `python -m uvicorn app.main:app --port 8000` | 8000 | `http://localhost:8000/health` | HTTP 200 OK | **PASS** |
| **Identity Service** | `services/identity-service` | `python -m uvicorn app.main:app --port 8001` | 8001 | `http://localhost:8001/health` | HTTP 200 OK | **PASS** |
| **Fraud Service** | `services/fraud-service` | `python -m uvicorn app.main:app --port 8002` | 8002 | `http://localhost:8002/health` | HTTP 200 OK | **PASS** |
| **Recovery Service** | `services/recovery-service` | `python -m uvicorn app.main:app --port 8003` | 8003 | `http://localhost:8003/health` | HTTP 200 OK | **PASS** |
| **Hardhat EVM** | `blockchain` | `npx hardhat node` | 8545 | `POST http://localhost:8545` (RPC) | Chain ID 31337 | **PASS** |
| **Web Cockpit** | `apps/web` | `npm run dev` | 5173 | `http://localhost:5173/` | HTTP 200 OK | **PASS** |
| **Docker Stack** | Root | `docker compose up --build` | 3000/8000 | Automated Compose healthchecks | Docker not installed on Windows host | **NOT APPLICABLE (Host Process Mode Active)** |

---

## 5. Database Reproducibility & State Independence

1. **MongoDB Mode**: When containerized or connected to MongoDB, `IDENTITY_MONGO_ENABLED=true` enables typed collections with unique indexes (`did`, `wallet_address`, `statusListIndex`, `canonical_hash`).
2. **Offline Development Mode**: When MongoDB is inactive (e.g. host running without Docker daemon), `IDENTITY_MONGO_ENABLED=false` automatically activates the in-memory / fake-Mongo persistence adapter.
3. **Synthetic User Provider**: Five synthetic Argon2id fixture accounts (`holder@example.test`, `issuer@example.test`, `verifier@example.test`, `admin@example.test`) are instantiated deterministically without requiring pre-seeded database rows.
4. **State Independence**: Tests and startup workflows run with 100% independence from any pre-existing local database state.
5. Status: **`PASS`**

---

## 6. Smart Contract Local Deployment

- **Toolchain**: Hardhat 2.29.1, Solidity 0.8.28, OpenZeppelin v5.
- **Contract Suite**:
  1. `DIDRegistry.sol` (DID document hash registration and ownership transfer)
  2. `RevocationRegistry.sol` (Bitstring Status List root hash anchoring)
  3. `EmergencyRecovery.sol` (3-of-5 / 2-of-3 threshold multi-sig recovery and AI quarantine)
  4. `AuditLogger.sol` (Tamper-evident security event anchoring)
- **Compilation**: Compiled 8 Solidity files successfully into `blockchain/artifacts/`.
- **Contract Tests**: 19 tests pass in under 2 seconds.
- Status: **`PASS`**

---

## 7. Reproducibility Assessment Conclusion

The Secure SSI Platform can be cloned, configured from templates, built, and executed cleanly without relying on any undocumented or hidden local state.
