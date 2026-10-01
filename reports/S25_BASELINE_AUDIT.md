# S25 Baseline & Environment Audit Report

**Project**: Academic Secure SSI Platform (Graduation Thesis Reference Implementation)  
**Author / Engineer**: Senior Release QA, Reproducibility, Security Verification & GitHub Release Engineer  
**Institution**: Sakarya University of Applied Sciences (SUBU)  
**Date**: October 1, 2026  
**Repository**: `C:\Users\besna\OneDrive\Bureau\secure-ssi-platform`  
**Git Branch**: `main`  
**Baseline HEAD**: `acd4f42` (`docs(s24): add thesis report structure and final report`)

---

## 1. Initial Git Repository State

| Parameter | Observed Value | Status |
|---|---|---|
| **Repository Path** | `C:\Users\besna\OneDrive\Bureau\secure-ssi-platform` | **VERIFIED** |
| **Active Branch** | `main` | **VERIFIED** |
| **HEAD Commit** | `acd4f42` | **VERIFIED** (Matches expected S24 completion HEAD) |
| **Origin Remote** | `https://github.com/charafeddine99/secure-ssi-platform.git` | **VERIFIED** |
| **Working Tree State** | Clean (0 uncommitted files, 0 untracked files) | **VERIFIED** |
| **Branch Tracking State** | Ahead of `origin/main` by 25 commits | **PENDING REMOTE SYNCHRONIZATION** |

### Recent Git Commit History (Last 10 Commits):
1. `acd4f42` (HEAD -> main) `docs(s24): add thesis report structure and final report`
2. `6372280` `docs(s24): add screenshot evidence matrix`
3. `43ba8d0` `docs(s24): add diagrams and protocol flows`
4. `f121ee3` `docs(s24): add architecture and system documentation`
5. `b6fddfa` `feat(s23): prepare professional demo environment`
6. `6516244` `feat(s22): finalize professional SSI user experience`
7. `db0bbcf` `docs(s21): add comprehensive standards and conformance validation report`
8. `630188b` `fix(typing): broaden encode_status_list revoked_indices type annotation to accept generic Collection and Iterable`
9. `125dc99` `fix(typing): resolve static type narrowing diagnostics in benchmark runner and test suites`
10. `eafaa79` `feat(s20): add performance benchmarks and optimization`

---

## 2. Host System & Toolchain Telemetry

All toolchain versions were directly probed on the Windows execution environment:

| Runtime / Tool | Detected Version | Execution Path / Invocation Method | Notes |
|---|---|---|---|
| **Operating System** | Windows 11 (win32 / x86_64) | Native Windows Shell (PowerShell) | Protected project `secure-door-project` excluded |
| **Node.js** | `v24.19.0` | `node.exe` on System PATH | Modern LTS / Current |
| **npm** | `11.17.0` | `npm.cmd` | Invoked via `.cmd` wrapper to avoid PowerShell script execution restriction |
| **Python (.venv)** | `Python 3.11.16` | `.\.venv\Scripts\python.exe` | Project-isolated virtual environment |
| **Python (System)** | `Python 3.11` | `C:\Users\besna\.local\bin\python3.11.exe` | Managed Python runtime |
| **pip** | `pip 26.2.1` | `python3.11 -m pip` | Modern package installer |
| **uv Package Manager** | `uv 0.12.19` | `uv.exe` on System PATH | High-speed Python dependency resolver |
| **Docker Engine** | **NOT INSTALLED** | CLI command not found | Host environment relies on native process execution |
| **Docker Compose** | **NOT INSTALLED** | CLI command not found | Host environment relies on native process execution |
| **Hardhat Toolchain** | `2.29.1` | `npx.cmd hardhat` in `blockchain/` | Local EVM simulation & smart contract testing |
| **Java / JDK** | **NOT INSTALLED** | CLI command not found | Not required for core TypeScript/Python/Solidity stack |
| **MongoDB Runtime** | Offline Fallback Active | Port 27017 inactive; in-memory/fake-Mongo active | Unit & integration tests execute without external MongoDB daemon |

---

## 3. Required Service Topology & Port Allocation

The platform defines the following service ports across microservices and clients:

| Service / Component | Documented Port | Protocol | Health / Probe Endpoint |
|---|---|---|---|
| **API Gateway Facade** | `8000` | HTTP / REST | `GET http://localhost:8000/health` |
| **Identity & SSI Core** | `8001` | HTTP / REST | `GET http://localhost:8001/health` |
| **AI Fraud Detection Engine** | `8002` | HTTP / REST | `GET http://localhost:8002/health` |
| **Guardian Social Recovery** | `8003` | HTTP / REST | `GET http://localhost:8003/health` |
| **Hardhat EVM Blockchain** | `8545` | JSON-RPC | `POST http://localhost:8545` (`eth_chainId`) |
| **Web Frontend (Vite / Dev)**| `5173` | HTTP | `GET http://localhost:5173/` |
| **Web Frontend (Docker / Prod)**| `3000` | HTTP | `GET http://localhost:3000/` |
| **MongoDB Community Server**| `27017` | MongoDB Wire | Connection string `mongodb://localhost:27017` |

---

## 4. Environment Templates & Configuration Manifests

The repository cleanly isolates secrets by committing only template files:

| Directory / Package | Template File | Primary Variables Declared (Redacted) |
|---|---|---|
| **Root Repository** | `.env.example` | `IDENTITY_MONGO_URI`, `JWT_SECRET`, `RECOVERY_GRANT_SECRET` |
| **`apps/web`** | `apps/web/.env.example` | `VITE_API_GATEWAY_URL`, `VITE_ENVIRONMENT` |
| **`blockchain`** | `blockchain/.env.example` | `HARDHAT_NETWORK`, `LOCAL_RPC_URL` |
| **`services/api-gateway`** | `services/api-gateway/.env.example` | `GATEWAY_PORT`, `IDENTITY_SERVICE_URL`, `FRAUD_SERVICE_URL` |
| **`services/identity-service`** | `services/identity-service/.env.example` | `IDENTITY_MONGO_ENABLED`, `IDENTITY_AUTH_JWT_SECRET` |
| **`services/fraud-service`** | `services/fraud-service/.env.example` | `FRAUD_SERVICE_PORT`, `MODEL_WEIGHT_XGB`, `MODEL_WEIGHT_AE` |
| **`services/recovery-service`**| `services/recovery-service/.env.example` | `RECOVERY_MONGO_ENABLED`, `RECOVERY_JWT_SECRET` |

### Dependency Manifests Detected:
1. `package.json` (Root repository monorepo manifest)
2. `apps/web/package.json` (React 18, Vite 6, Lucide, QRCode)
3. `apps/web/package-lock.json` (Frozen dependency graph)
4. `blockchain/package.json` (Hardhat, Ethers, Solidity 0.8.28)
5. `blockchain/package-lock.json` (Frozen blockchain dependency graph)
6. Python virtual environment at `.venv/` containing pre-installed packages for `fastapi`, `pydantic`, `cryptography`, `pytest`, `httpx`, `xgboost`, `torch`, `web3`.

---

## 5. Baseline Audit Conclusion

The initial repository state is fully consistent with the S24 completion baseline (`acd4f42`). No untracked or uncommitted changes exist. The environment is verified and ready for Phase 2 secret scanning and clean reproducibility testing.
