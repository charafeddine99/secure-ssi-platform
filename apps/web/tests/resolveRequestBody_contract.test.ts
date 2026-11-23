import assert from "node:assert/strict";
import { resolveOid4vpRequestLink } from "../src/api/presentation.ts";

// The wallet must send the scanned link as a JSON object. A string body, such as
// a double-encoded one, is refused by the server with 422.
const originalFetch = globalThis.fetch;
const previousLocalStorage = globalThis.localStorage;
// The signed-in marker the client checks before sending; the session itself is an HttpOnly cookie.
globalThis.localStorage = {
  getItem: (key: string) => (key === "ssi_session_active" ? "1" : null),
  setItem: () => undefined,
  removeItem: () => undefined,
  clear: () => undefined,
  key: () => null,
  length: 0,
} as Storage;
const link = "openid4vp://?client_id=decentralized_identifier%3Adid%3Ajwk%3Ae30&request_uri=https%3A%2F%2Fwallet.example%2Fapi%2Fv1%2Foid4vp%2Frequest-objects%2Fsession_x";
let sent: RequestInit | undefined;
try {
  globalThis.fetch = async (_input, init = {}) => {
    sent = init;
    return new Response(JSON.stringify({ sessionId: "session_x", clientId: "decentralized_identifier:did:jwk:e30" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const result = await resolveOid4vpRequestLink(link);
  assert.equal(result.sessionId, "session_x");
  assert.equal(sent?.method, "POST");
  const body = JSON.parse(String(sent?.body));
  assert.equal(typeof body, "object", "the body is a JSON object, not a JSON string");
  assert.deepEqual(body, { link }, "the body holds exactly the scanned link");
} finally {
  globalThis.fetch = originalFetch;
  globalThis.localStorage = previousLocalStorage;
}
