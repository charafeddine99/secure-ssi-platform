import { parseCredentialOfferUri } from "../src/pages/holder/offerUri.ts";

let assertions = 0;

function equal(actual: unknown, expected: unknown, message: string): void {
  assertions += 1;
  if (actual !== expected) throw new Error(`${message}: expected ${String(expected)}, received ${String(actual)}`);
}

const GRANT = "urn:ietf:params:oauth:grant-type:pre-authorized_code";
const link = (grant: Record<string, unknown>) =>
  "openid-credential-offer://?credential_offer=" + encodeURIComponent(JSON.stringify({
    credential_issuer: "https://issuer.example.test",
    credential_configuration_ids: ["UniversityAffiliationCredential"],
    grants: { [GRANT]: { "pre-authorized_code": "code-123", ...grant } },
  }));

// OpenID4VCI 1.0: a tx_code object means the wallet must ask for the code.
const withTxCode = parseCredentialOfferUri(link({ tx_code: { input_mode: "numeric", length: 4, description: "Code from the issuer" } }));
equal(withTxCode.requiresTxCode, true, "tx_code asks for a transaction code");
equal(withTxCode.txCodeDescription, "Code from the issuer", "tx_code description is shown");

// Offers created before the fix carry the older user_pin_required flag.
equal(parseCredentialOfferUri(link({ user_pin_required: true })).requiresTxCode, true, "legacy user_pin_required asks for a code");
equal(parseCredentialOfferUri(link({ user_pin_required: false })).requiresTxCode, false, "user_pin_required false needs no code");
equal(parseCredentialOfferUri(link({})).requiresTxCode, false, "no tx_code needs no code");

console.log(`offerUri: ${assertions} assertions passed`);
