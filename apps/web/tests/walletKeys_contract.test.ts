import { fetchWalletKeys, parseWalletKeys } from "../src/api/keys.ts";
import { fetchCredentialHistory, parseCredentialHistory } from "../src/api/status.ts";

let assertions = 0;
function ok(value: unknown, message: string): asserts value {
  assertions += 1;
  if (!value) throw new Error(message);
}
function throws(fn: () => unknown, message: string): void {
  assertions += 1;
  try { fn(); } catch { return; }
  throw new Error(message);
}

const WALLET = "wallet_AAAAAAAAAAAAAAAAAAAA";
const key = {
  keyId: "key_1", walletId: WALLET, ownerUserId: "u1", holderDid: "did:key:z6Mk", provider: "local",
  algorithm: "Ed25519", purpose: "assertionMethod", keyVersion: 1, state: "ACTIVE",
  publicKeyMultibase: "z6Mk", fingerprint: "fp", verificationMethod: "did:key:z6Mk#z6Mk",
  createdAt: "2026-10-29T10:00:00Z", updatedAt: "2026-10-29T10:00:00Z", activatedAt: null, rotatedAt: null,
  suspendedAt: null, revokedAt: null, destroyedAt: null, destructionScheduledAt: null, expiresAt: null,
  predecessorKeyId: null, successorKeyId: null, version: 1,
};

// Wallet keys: strict shape, bound to the requested wallet, no private fields carried over.
const keys = parseWalletKeys({ walletId: WALLET, items: [key], nextCursor: null }, WALLET);
ok(keys.length === 1 && keys[0].state === "ACTIVE" && keys[0].fingerprint === "fp", "valid key list parses");
ok(!("publicKeyMultibase" in keys[0]) && !("ownerUserId" in keys[0]), "only display fields are kept");
throws(() => parseWalletKeys({ walletId: "wallet_other", items: [key], nextCursor: null }, WALLET), "a list for another wallet is rejected");
throws(() => parseWalletKeys({ walletId: WALLET, items: [{ ...key, walletId: "wallet_other" }], nextCursor: null }, WALLET), "a foreign key item is rejected");
throws(() => parseWalletKeys({ walletId: WALLET, items: "nope" }, WALLET), "a malformed list is rejected");

// Credential history: oldest first, status normalised, malformed events rejected.
const history = parseCredentialHistory({
  credentialId: "urn:uuid:1", currentStatus: "REVOKED", totalEvents: 2,
  events: [
    { eventId: "e2", eventType: "CREDENTIAL_REVOKED", subjectId: "urn:uuid:1", actorId: "u", correlationId: null, createdAt: "2026-10-29T11:00:00Z", metadata: { status: "REVOKED" } },
    { eventId: "e1", eventType: "STATUS_CHECKED", subjectId: "urn:uuid:1", actorId: null, correlationId: null, createdAt: "2026-10-29T10:00:00Z", metadata: {} },
  ],
});
ok(history.currentStatus === "REVOKED" && history.events[0].eventId === "e1", "events are ordered oldest first");
throws(() => parseCredentialHistory({ credentialId: "x", currentStatus: "ACTIVE", events: [{ eventId: "e" }] }), "an event without type/time is rejected");

// Both calls go to the real routes with the session cookie and fail before the network when signed out.
const previousFetch = globalThis.fetch;
const previousStorage = globalThis.localStorage;
const calls: Array<{ url: string; init?: RequestInit }> = [];
let signedIn = true;
globalThis.localStorage = {
  getItem: (k: string) => (k === "ssi_session_active" && signedIn ? "1" : null),
  setItem: () => undefined, removeItem: () => undefined, clear: () => undefined, key: () => null, length: 0,
};
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  calls.push({ url: String(input), init });
  if (String(input).endsWith("/keys")) return new Response(JSON.stringify({ walletId: WALLET, items: [key], nextCursor: null }), { status: 200 });
  return new Response(JSON.stringify({ credentialId: "urn:uuid:1", currentStatus: "ACTIVE", events: [] }), { status: 200 });
}) as typeof globalThis.fetch;
try {
  await fetchWalletKeys(WALLET);
  ok(calls[0].url.endsWith(`/api/v1/identity/wallets/${WALLET}/keys`) && calls[0].init?.credentials === "include", "keys use the owner route and session cookie");
  await fetchCredentialHistory("urn:uuid:1");
  ok(calls[1].url.endsWith("/api/v1/identity/credentials/urn%3Auuid%3A1/history"), "history uses the encoded credential route");
  signedIn = false;
  let failedClosed = false;
  try { await fetchWalletKeys(WALLET); } catch { failedClosed = true; }
  ok(failedClosed && calls.length === 2, "signed-out key lookup sends no request");
} finally {
  globalThis.fetch = previousFetch;
  globalThis.localStorage = previousStorage;
}

console.log(`Wallet key and credential history contracts: ${assertions} passed, 0 failed.`);
