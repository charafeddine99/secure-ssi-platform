# 08 – External Dependencies

Items that could not be verified in this audit because they need a device, a service, an account or an authority outside the local machine. None is marked VERIFIED.

| Item | Needed for | What exists in the code | What was tested instead | What is needed |
|---|---|---|---|---|
| Physical phone | QR cross-device flow on a real camera and network | Complete QR/request_uri flow | Two isolated browsers, QR decoded from the real canvas with jsQR (13/13); request_uri reachable from outside the stack (FIX-1 check) | A phone plus a public HTTPS address (`IDENTITY_PUBLIC_ORIGIN`), e.g. a temporary tunnel, with the user's approval |
| Public HTTPS address | Phone tests; production `https` origin | Public-origin settings with phone-reachability and HTTPS-in-production guards | Not available | Domain or tunnel and a certificate |
| Real WebAuthn authenticator | Passkey / security key with a real device | WebAuthn registration and step-up | Virtual authenticator only | A phone passkey or a hardware security key |
| External KMS / HSM | Production key custody | Generic remote KMS client, signing-trust gates | Development software provider | A KMS/HSM account and its endpoint |
| Blockchain node | Hash anchoring | Contracts, `web3_bridge.py`, anchoring API | Unit tests with fakes; 5 live tests skipped | A local Hardhat node (port 8545) or a testnet account, `BLOCKCHAIN_ENABLED=true` |
| OpenID conformance suites | Formal OID4VCI/OID4VP conformance | Protocol implementation | Platform tests only | Access to the OpenID Foundation conformance suite and a public endpoint |
| Labelled real security data | Training and validating an ML risk model | Rule-based scoring only (no model) | – | Real or published labelled data (planned TÜBİTAK work) |
| Independent penetration test, legal review | Production readiness | – | – | External parties |

## Local environment limits met during the audit

| Limit | Effect | Handling |
|---|---|---|
| Windows Smart App Control (on) | Blocks unsigned native Python modules in `.venv` (`cbor2`, sometimes scikit-learn) | Identity tests ran in a container; settings not changed |
| OneDrive Files On-Demand | A `node_modules` file was online-only, so a Docker build for the DR stack failed | DR stack reused the already-built images |
| OneDrive / outside change | During the audit a Desktop rollback folder was removed and 37 old web files reappeared | Files moved (not deleted) to `C:\Users\besna\secure-ssi-audit-rollback-20261121\restored-old-web-files` with the user's approval; new rollback copy kept outside OneDrive |
| Gateway per-IP rate limit | All test traffic comes from one IP | Isolated Redis counters cleared between stages; the limit itself was not changed |
