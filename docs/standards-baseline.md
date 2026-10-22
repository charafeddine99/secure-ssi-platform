# Standards Baseline

Reviewed on 2026-10-13 against official primary sources. The selected profile is unchanged; source review is not a conformance claim.

| Area | Selected baseline | Status at review | Prototype use |
| --- | --- | --- | --- |
| DID data model | [DID Core v1.0](https://www.w3.org/TR/did-core/) | W3C Recommendation, 19 July 2022 | Required |
| DID Core next version | [DID Core v1.1](https://www.w3.org/TR/did-core/all/) | Candidate Recommendation Snapshot, 5 March 2026 | Monitor only |
| DID resolution | [DID Resolution v0.3](https://www.w3.org/TR/did-resolution/) | W3C Working Draft | Interface guidance only |
| Institutional DID method | [`did:web`](https://w3c-ccg.github.io/did-method-web/) | Unofficial community draft | Synthetic issuer |
| Holder fixture DID method | [`did:key` v0.9](https://w3c-ccg.github.io/did-key-spec/) | Community draft | Short-lived synthetic fixture only |
| Credential data model | [VC Data Model v2.0](https://www.w3.org/TR/vc-data-model-2.0/) | W3C Recommendation, 15 May 2025 | Required |
| Credential next version | [VC Data Model v2.1](https://www.w3.org/TR/vc-data-model/all/) | W3C Working Draft, 11 May 2026 | Monitor only |
| Embedded proof model | [VC Data Integrity v1.0](https://www.w3.org/TR/vc-data-integrity/) | W3C Recommendation, 15 May 2025 | Required |
| EdDSA proof suite | [Data Integrity EdDSA v1.0](https://www.w3.org/TR/vc-di-eddsa/) | W3C Recommendation, 15 May 2025 | `eddsa-jcs-2022` |
| Status list next version | [Bitstring Status List v1.1](https://www.w3.org/TR/vc-bitstring-status-list/all/) | First Public Working Draft, 24 September 2026 | Monitor only; v1.0 remains frozen |
| Status list selected version | [Bitstring Status List v1.0](https://www.w3.org/TR/vc-bitstring-status-list/) | W3C Recommendation, 15 May 2025 | Required |
| Canonicalization | [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785) | RFC, Informational, June 2020 | Required by selected suite |
| Signature primitive | [RFC 8032 EdDSA](https://www.rfc-editor.org/rfc/rfc8032) | RFC, Informational, January 2017 | Ed25519 |
| Credential issuance protocol | [OpenID4VCI 1.0](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html) | Final; latest errata-corrected text, published 16 September 2025 | Frozen project profile; independent interoperability not established |
| Credential presentation protocol | [OpenID4VP 1.0](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html) | Final; latest errata-corrected text | DCQL project profile; independent interoperability not established |
| OAuth security guidance | [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) | IETF Best Current Practice 240, January 2025 | Security review baseline; not a certification |
| Web application security | [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS/releases) | Latest stable release confirmed on 13 October 2026 | Verification checklist; no ASVS assessment claimed |
| Accessibility | [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | W3C Recommendation; also ISO/IEC 40500:2025 | Audit baseline; no WCAG conformance claimed |
| EUDI reference comparison | [EUDI Wallet Reference Implementation](https://docs.eudi.dev/latest/reference-implementation/feature-map/) | Mutable `latest` documentation; comparison source only | Not the Secure SSI profile and not proof of EUDI conformance |

## Update policy

- Recheck this table before beginning a new implementation milestone.
- Draft updates require a new ADR before adoption.
- Errata and implementation reports must be reviewed before claiming conformance.
- Method-specific community drafts require separate risk acceptance.
- The v1.1 status-list publication is a monitor item only; this review did not change the frozen v1.0 profile.
