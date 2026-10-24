# Secure SSI Platform V2.1 — WP-10 Blockchain Anchor Security

**Verification date:** 24 October 2026 | **Branch:** `besna-dev` | **Code baseline:** `9e965bb4de7f5e1bb1cbf0f48f30d53ebfb88b73` plus this WP-10 contract fix
**Decision:** **PARTIAL for current-source G10**

## Scope and finding

WP-10/G10 covers optional hash-only integrity anchors whose confirmed state must be based on an actual transaction receipt. Chain status must remain separate from credential validity.

The existing `RevocationRegistry` stored a global irreversible revocation by credential hash, but `revokeCredential` had no caller authorization. The contract already declared an `owner` and `onlyOwner` modifier, but did not apply it to this write. Any account able to obtain a credential hash could therefore revoke that hash on-chain. This was confirmed by inspecting the public function and then adding a failing non-owner transaction regression.

`revokeCredential` now uses the existing `onlyOwner` modifier. The new Hardhat test verifies that an unauthorized caller receives the contract's authorization revert and that the credential remains unrevoked; the existing owner-write and duplicate-revocation checks remain. `anchorStatusList` retains its per-sender namespace, and the Identity bridge continues to store only digests in contract calls.

This is a single-owner prototype authorization rule, not a multi-issuer role registry. The deploying owner and Identity Service transaction signer must match. A source change does not modify already deployed, non-upgradeable bytecode; affected deployments require a new contract address/configuration before relying on the access check.

## Standards context

OpenZeppelin describes `onlyOwner` as restricting a function to the account that owns the contract, initially set by the deployer. The existing project contract implements a small custom equivalent; this report does not claim OpenZeppelin library use or formal conformance. OWASP lists SCSVS v0.0.1 as its latest stable release; the access-control regression is a project check informed by that security-verification approach, not an OWASP certification. [OpenZeppelin access control](https://docs.openzeppelin.com/contracts/5.x/access-control), [OWASP SCSVS](https://owasp.org/projects/smart-contract-security-verification-standard).

## Executed evidence

| Command / observation | Result | Boundary |
|---|---|---|
| `npm.cmd test --prefix blockchain` | **20 passing, 0 failing.** Hardhat compiled one Solidity file with Solidity 0.8.28; includes owner revocation, non-owner rejection, unchanged state after rejection, duplicate rejection, and the rest of the contract suite. | In-process Hardhat network; not a public network audit. The compiler was downloaded into the local tool cache because it was absent; repository package versions/lockfiles were not changed. |
| CWD `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/unit/test_blockchain_anchor.py` | **8 passed, 0 failed; 1 existing SQLite deprecation warning.** | Unit-level hash/redaction, state transitions, offline, pending/reverted receipt, and bridge call handling. |
| CWD `services/identity-service`: `..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_blockchain_anchoring.py`, with `BLOCKCHAIN_ENABLED=true` and the local Hardhat signer key in the process environment | **7 passed, 0 failed, 0 skipped; 1 existing SQLite deprecation warning.** | Ephemeral loopback chain ID 1337, four current compiled contracts deployed at deterministic local test addresses, FakeDatabase persistence. Tested current-source DID/status-list/revocation/quarantine/audit receipts and digest-only payload. The Hardhat process was stopped after the test; deployment metadata was not written. |
| `..\..\.venv\Scripts\python.exe -m pytest -q tests/integration/test_golden_path.py::test_golden_path_complete_lifecycle` | **BLOCKED: interrupted without a pytest summary.** The process stalled in the Windows TestClient/asyncio Proactor path, consistent with the earlier `socketpair`/`socket.accept` environment blocker. | Does not count as a pass or failure. The test source asserts that an absent optional anchor remains `blockchainAnchored == false` while the valid credential's policy result remains `ACCEPTED`, but this current-source assertion was not re-executed. |

The three completed suites contain **35 passing tests total** (20 + 8 + 7), with **0 failures and 0 skips**; warnings are as shown above. Their counts are reported separately because they cover different layers.

## Acceptance decision and remaining work

Current-source receipt creation, digest-only calls, owner-only revocation, unauthorized rejection, offline/pending/reverted states, and the live local-chain bridge path passed their focused tests. G10 remains **PARTIAL** because the current-source Golden Path assertion that offline/unanchored verification remains accepted could not be executed on this Windows host. The old G10 live run in earlier evidence is retained as historical evidence and does not replace this current-source attempt.

No public-chain deployment, verification of an already-deployed address, multi-issuer authorization model, production key custody, formal contract audit, or production-readiness claim is made. The new source protection applies only after redeployment; configure the Identity signer to the deployment owner and validate the deployed bytecode before using credential-revocation transactions.

## Changed files

- `blockchain/contracts/RevocationRegistry.sol` — restrict credential revocation to owner.
- `blockchain/test/SSIContracts.test.ts` — unauthorized caller regression.
- `README.md` — update the test count and current WP-10 summary/link.
- `docs/blockchain_anchoring.md` — describe authorization and redeployment boundary.
- `docs/implementation/SECURE_SSI_PLATFORM_GATE_ACCEPTANCE.md` — current G10 status/evidence.
- `docs/implementation/SECURE_SSI_PLATFORM_TEST_EVIDENCE.md` — exact commands and results.
- `reports/V2_1_WP10_BLOCKCHAIN_ANCHOR_SECURITY.md` — this evidence report.
