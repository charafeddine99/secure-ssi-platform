# Secure SSI Platform — Design / Architecture Report (Revised)

**Date:** 5 October 2026  
**Status:** Independent review revision of the V2.1 architecture, aligned with the frozen implementation profile.  
**Does not claim:** that the current repository already implements this design at L3.

This report matches the revised master plan. Protocol diagrams describe the **selected** standards, not a mix of thesis-era Indy/Aries and V2.1 OpenID.

---

## 1. Purpose and limitations

The platform is a **web SSI ecosystem prototype** for academic demonstration of:

- W3C VC 2.0 issuance and presentation,
- OpenID4VCI/OID4VP 1.0 credential exchange (restricted profile),
- explainable trust and status,
- guardian recovery as a **project-specific** control,
- heuristic or trained-if-evidenced risk scoring,
- optional EVM integrity anchoring.

**Limitations (honest):**

- Not EUDI-certified; ARF v3.0.0 is an architectural reference only.
- Not connected to government identity providers.
- Not a hardware wallet; KeyCustody is software.
- Not ZKP/BBS+; claim minimization only.
- Not Hyperledger Indy/Aries/DIDComm.
- Not EIP-4337 account abstraction as identity.
- Interoperability with third-party wallets is not guaranteed until Interop B evidence exists for the **same credential format**.

---

## 2. Product and role model

See the revised master plan §1. The architecture is **role-separated**:

| Actor | Analog in EUDI/walt.id | This prototype |
| --- | --- | --- |
| Wallet | EUDI Wallet / walt.id Wallet2 | Web Holder app + wallet domain |
| Issuer | PID/EAA issuer / Issuer2 | Issuer Portal + credential/OID4VCI domain |
| Relying party | RP / Verifier2 | Verifier Portal + OID4VP domain |
| Trust infrastructure | Trusted lists / LoTEs | **Local Trust Registry** (project profile) |
| Wallet provider ops | WP backend | Admin + SSI Core |

This analogy is pedagogical. Trusted lists (ETSI TS 119 612) and LoTEs (ETSI TS 119 602) are **out of scope**.

---

## 3. Logical architecture

```
[ Public web ]
[ Holder | Issuer | Verifier | Guardian | Admin ]  ← UI; no private keys in DOM storage as plaintext product requirement
        |
        v
[ API Gateway ]  authn, RBAC, validation, rate limit, correlation id
        |
        +-- Identity domain (account, DID, KeyCustody port)
        +-- Wallet domain (offers, credentials, consent, activity)
        +-- Credential domain (templates, VC 2.0 documents, Data Integrity, status lists)
        +-- Exchange domain (OID4VCI sessions, OID4VP sessions, DCQL)
        +-- Trust domain (registry records, evidence, status)
        +-- Consent/Policy domain
        +-- Risk domain (fraud-service; advisory)
        +-- Recovery domain (quorum, timelock, rotation)
        +-- Audit domain
        +-- Integrity domain (canonical hash, EVM adapter)
        |
[ MongoDB authoritative ] [ Redis ephemeral ] [ optional EVM testnet ]
```

**UI model:** one responsive web app, route-separated by role, shared design system, SSI-specific components (QR, credential card, verification matrix, consent, recovery timeline). Terminology on screen must match backend enums (VALID/INVALID/REVOKED/EXPIRED/UNTRUSTED/HIGH_RISK, etc.).

---

## 4. Wallet model

The Wallet is an identity component:

- Holds **references** to key material via KeyCustody (no private key in API responses or screenshots).
- Displays DID and verification method.
- Stores issued VCs as received (canonical bytes/JSON used for later verification).
- Evaluates DCQL against stored credentials.
- Records consent and builds a VP whose disclosed claims match consent.
- Signs holder-binding material fail-closed.
- Surfaces issuance/presentation session states, including failure.

**Custody assumption:** server-mediated keys for the prototype. If keys were only in the browser, recovery and multi-device would be different; that design is not claimed.

---

## 5. DID and key model

- Documents follow DID Core 1.0 + Controlled Identifiers 1.0 verification methods (`Multikey` as in ADR 0002).
- **Issuer:** `did:web` resolved over HTTPS (or labeled demo fixture with the same port).
- **Holder prototype:** `did:key` derived from Ed25519 public key; no in-method rotation.
- Recovery creates a **new** holder key/DID and retires the old verification relationship in platform state (and status/revocation of credentials as policy requires). It cannot “update” `did:key`.
- Verifier discovers `assertionMethod` / authentication material by resolution, not by trusting a DID string prefix.

---

## 6. Credential and proof model

```
Unsigned VC (VC 2.0 claims)
  -> Data Integrity add proof
       type: DataIntegrityProof
       cryptosuite: eddsa-jcs-2022
       proofPurpose: assertionMethod
       verificationMethod: issuer DID URL
       proofValue: Ed25519 over JCS canonicalization
```

Verification (fail-closed):

1. Resolve `verificationMethod`.
2. Confirm relationship allows `assertionMethod`.
3. Canonicalize per `eddsa-jcs-2022` (RFC 8785).
4. Verify Ed25519. Exception or missing proof ⇒ invalid.
5. Check `validFrom` / `validUntil`.
6. Fetch Bitstring Status List 1.0; corrupt/unavailable ⇒ profile fail-closed (do not accept).
7. Separate trust lookup.

**Do not** treat `proof` field presence as verification.  
**Do not** omit signed claims and still present the original issuer proof as valid (claim omission on a non-SD Data Integrity VC invalidates the proof). If the profile only supports whole-credential presentation plus **not sending extra credentials**, say so. If claim-level omission is offered, the implementation must either (a) use a cryptographic SD format (out of scope) or (b) have the **issuer** issue a new credential containing only permitted claims, or (c) present the full signed VC while the **verifier UI** displays only requested claims **without claiming the payload was minimized cryptographically**. The revised plan prefers **honest option (c) or issuer-side subset credentials**, not breaking signatures.

This is a **design correction** relative to UI that implied field-level SD on `eddsa-jcs-2022`.

---

## 7. OID4VCI sequence (Final)

```
Issuer publishes metadata
  /.well-known/openid-credential-issuer
  includes token_endpoint, credential_endpoint, nonce_endpoint,
  credential_configurations_supported, proof_types_supported: jwt

Issuer creates offer
  grants.pre-authorized_code (single use, expiry)

Wallet validates offer (issuer URL, config id, grant)

Wallet POST token_endpoint
  grant_type=urn:ietf:params:oauth:grant-type:pre-authorized_code
  -> access_token

Wallet POST nonce_endpoint
  -> { c_nonce }

Wallet builds jwt proof (typ openid4vci-proof+jwt, aud=issuer, nonce=c_nonce)

Wallet POST credential_endpoint
  Authorization: Bearer access_token
  proofs.jwt = [ proof ]
  -> credential (VC + Data Integrity proof)

Wallet persists credential and shows it
```

Same-device: offer link in the same browser. Cross-device: QR of the offer URI.

---

## 8. OID4VP + DCQL sequence (Final)

```
Verifier creates session
  client_id, state, nonce, response_mode=direct_post,
  dcql_query { credentials: [ { id, format, meta, claims? } ] }

Transport
  QR (cross-device) or HTTPS link (same-browser)

Wallet
  parse request
  evaluate DCQL against stored credentials
  show purpose, verifier identity, matched credential, requested claims
  holder consent
  create VP (Data Integrity on VP and/or embedded VC proofs per profile tests)
  POST direct_post with vp_token, state

Verifier
  bind state/nonce/client
  consume nonce (single use)
  verify VC + holder binding
  trust, status, expiry, policy, AI
  show matrix, not a single unexplained badge
```

DCQL evaluation is **wallet-side**. A hardcoded claim checklist is non-conformant for this profile.

---

## 9. Trust model

```
TrustRecord
  issuer_did
  organization_id
  source (admin_seeded | documented_manual)
  status (active | suspended | revoked)
  valid_from / valid_until
  policy_ref
  record_id
  evidence_uri (demo-appropriate)
```

Verification reads TrustRecord. Absence ⇒ untrusted (fail-closed for the Golden Path policy).

**Not trust:** `did:web:` prefix, “we deployed a contract”, screenshot of a green badge, EU-looking hostname.

---

## 10. Status model

W3C Bitstring Status List 1.0:

- Status list credential as specified (encoded GZIP bitstring, minimum size rules).
- Retrieval over HTTPS; cache with explicit freshness policy (project: treat stale beyond configured TTL as fail-closed or “status unknown = not accepted”).
- Revocation bit set ⇒ non-acceptance on Golden Path.
- Privacy: do not create correlating unique status URLs per holder if avoidable; follow spec privacy considerations at prototype scale.

---

## 11. Recovery model (project-specific)

Not defined by W3C/OpenID. Design:

- Holder pre-registers N guardians; threshold M-of-N.
- RecoveryRequested → risk evaluate (advisory) → notify → collect approvals → threshold → timelock → executable → new KeyCustody key → new holder DID (`did:key` fixture or documented successor) → old key unusable for new presentations → audit.
- Abuse: duplicate guardian, unauthorized guardian, replayed approval, timelock skip, stale key after rotation — all reject.
- UX: timeline of states; no “password reset” language.

Blockchain may anchor the **completion hash**, not the recovery decision itself.

---

## 12. AI / risk model

- Input: protocol and application events (issuance velocity, failed auths, recovery attempts, verifier diversity) on **synthetic** data unless labeled otherwise.
- Output: independent risk signal.
- Decision: invalid crypto + any risk ⇒ REJECT; valid crypto + high risk ⇒ REVIEW/QUARANTINE per policy, not silent ACCEPT.
- If `fraud-service` remains formula-based, name it **heuristic engine**; do not show “trained autoencoder” or a single accuracy percentage from the thesis.

---

## 13. Integrity / blockchain model

```
Canonical event JSON (no PII)
  -> SHA-256
  -> EVM anchor tx (test network)
  -> off-chain { digest, tx, confirmations, status }
```

Proves: a digest was submitted at a time, if the tx is confirmed.  
Does **not** prove: credential validity, holder binding, issuer trust, or revocation.

UI: `anchor_status: none | pending | confirmed | failed`.

---

## 14. Security assumptions

- TLS in deployment; local HTTP only in explicitly labeled local demo.
- Gateway session/JWT for portals; object-level authz on foreign org resources.
- Rate limits on token, credential, nonce, direct_post, recovery approve.
- Fail-closed verification.
- Secrets and private keys never in frontend bundles, logs, or chain.
- Malicious verifier: over-request visible; consent can deny; no extra claims in VP beyond policy.
- Malicious issuer: unregistered issuer fails trust even if signature verifies under attacker key.

---

## 15. Mapping architecture to implementation sequence

G2 freezes this report. G3 implements wallet states. G4 implements §7. G5 implements §8. G6 implements §9–10 and the matrix. G7–G10 implement consent, recovery, risk, integrity. G11 proves they are one system. G12 aligns UI copy to this report. G14 tests Interop A against this profile.

---

## 16. Diagram inventory (textual; to be drawn in thesis from this report, not from the January mixed-stack figures)

1. Role diagram: Holder / Issuer / Verifier / Guardian / Admin / Trust / Integrity.  
2. OID4VCI sequence with Token + Nonce + Credential.  
3. OID4VP sequence with DCQL + direct_post.  
4. Verification matrix data flow.  
5. Recovery state machine.  
6. Explicit non-goals box.

January 2026 figures that show DIDComm, ACA-Py, Indy, EIP-4337 as the SSI path **must not** be reused as the current architecture.
