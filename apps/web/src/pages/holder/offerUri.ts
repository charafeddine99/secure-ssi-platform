/** Parsing of inline OID4VCI credential offers (credential_offer_uri is deliberately not fetched). */

export interface ParsedOffer {
  preAuthorizedCode: string;
  configurationId: string;
  issuer: string | null;
  requiresTxCode: boolean;
  txCodeDescription: string | null;
}

/** Parse an inline OID4VCI offer. credential_offer_uri is deliberately not fetched. */
export function parseCredentialOfferUri(uri: string): ParsedOffer {
  const url = new URL(uri.replace(/^openid-credential-offer:\/\//, "https://placeholder/"));
  const rawOffer = url.searchParams.get("credential_offer");
  if (!rawOffer) {
    throw new Error("This wallet supports inline credential_offer values only; credential_offer_uri links are not fetched.");
  }
  let parsed: {
    credential_issuer?: unknown;
    credential_configuration_ids?: unknown;
    grants?: Record<string, { "pre-authorized_code"?: unknown; tx_code?: { description?: unknown } } | undefined>;
  };
  try {
    parsed = JSON.parse(rawOffer);
  } catch {
    throw new Error("The credential offer is not valid JSON.");
  }
  const grant = parsed.grants?.["urn:ietf:params:oauth:grant-type:pre-authorized_code"];
  const code = grant?.["pre-authorized_code"];
  const ids = parsed.credential_configuration_ids;
  if (typeof code !== "string" || !code) throw new Error("The offer does not include a pre-authorized code.");
  if (!Array.isArray(ids) || ids.length !== 1 || typeof ids[0] !== "string") {
    throw new Error("This wallet claims exactly one credential configuration per offer.");
  }
  return {
    preAuthorizedCode: code,
    configurationId: ids[0],
    issuer: typeof parsed.credential_issuer === "string" ? parsed.credential_issuer : null,
    requiresTxCode: Boolean(grant?.tx_code),
    txCodeDescription: typeof grant?.tx_code?.description === "string" ? grant.tx_code.description : null,
  };
}
