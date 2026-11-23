/**
 * Classifies what a holder pasted or scanned. Nothing here fetches a URL: a
 * request is always loaded from our own API after this step.
 */
export type ScanInput =
  | { kind: "offer"; value: string }
  | { kind: "oid4vp"; value: string }
  | { kind: "handoff"; request: string }
  | { kind: "rejected"; reason: string };

const HANDOFF_PATH = "/wallet/present";
const SESSION = /^session_[A-Za-z0-9_-]{16,80}$/;
const MAX_LENGTH = 8192;

export function classifyScanInput(raw: string, ownOrigin: string): ScanInput {
  const value = raw.trim();
  if (!value) return { kind: "rejected", reason: "Paste the link from the issuer or the verifier." };
  if (value.length > MAX_LENGTH) return { kind: "rejected", reason: "This link is too long to be a request." };
  if (value.startsWith("openid-credential-offer://")) return { kind: "offer", value };
  if (value.startsWith("openid4vp://")) return { kind: "oid4vp", value };
  if (/^urn:uuid:/i.test(value)) {
    return { kind: "rejected", reason: "This is a credential identifier, not a request. Credentials are shared by scanning a verifier's QR code." };
  }
  if (/^did:/i.test(value)) {
    return { kind: "rejected", reason: "This is a DID, not a request. Ask the verifier for a QR code or link." };
  }
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return { kind: "rejected", reason: "Unrecognised link. Use an issuer offer or a verifier request." };
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    return { kind: "rejected", reason: "This kind of link is not accepted." };
  }
  if (url.origin !== ownOrigin) {
    return { kind: "rejected", reason: "This link belongs to another site. Open requests only from this platform." };
  }
  const request = url.searchParams.get("request") ?? "";
  if (url.pathname === HANDOFF_PATH && SESSION.test(request)) return { kind: "handoff", request };
  return { kind: "rejected", reason: "This page is not a presentation request." };
}
