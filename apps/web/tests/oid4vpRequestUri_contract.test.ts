import { hasRequestUri, parseOid4vpRequestSessionId } from "../src/utils/oid4vpRequestUri.ts";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function encodeInlineRequest(state = "session_1234567890abcdef12345678"): string {
  const params = new URLSearchParams({
    client_id: "http://identity-service:8000/verifier",
    response_uri: "http://localhost:8001/api/v1/oid4vp/response",
    response_type: "vp_token",
    response_mode: "direct_post",
    nonce: "synthetic-test-nonce",
    state,
    dcql_query: JSON.stringify({ credentials: [{ id: "credential_1" }] }),
  });
  return `openid4vp://?${params.toString()}`;
}

function expectInvalid(uri: string, message: string): void {
  let rejected = false;
  try {
    parseOid4vpRequestSessionId(uri);
  } catch {
    rejected = true;
  }
  assert(rejected, message);
}

assert(
  parseOid4vpRequestSessionId(encodeInlineRequest()) === "session_1234567890abcdef12345678",
  "the project's inline OID4VP request returns its server session state",
);
expectInvalid(
  "openid4vp://?client_id=x&request_uri=https%3A%2F%2Fevil.example%2Frequests%2Fsession_12345678",
  "a request_uri is never trusted from its URL path; the server must check it",
);
assert(
  hasRequestUri("openid4vp://?client_id=x&request_uri=https%3A%2F%2Fverifier.example%2Fr"),
  "a by-reference request is recognised",
);
assert(!hasRequestUri("https://verifier.example/?request_uri=x"), "only openid4vp links count as by-reference");
expectInvalid("openid4vp://?state=session_12345678", "an incomplete inline request is rejected");
expectInvalid(encodeInlineRequest("bad session id"), "a malformed inline state is rejected");
expectInvalid(
  encodeInlineRequest().replace("response_mode=direct_post", "response_mode=query"),
  "an unsupported response mode is rejected",
);
expectInvalid(
  encodeInlineRequest().replace(encodeURIComponent(JSON.stringify({ credentials: [{ id: "credential_1" }] })), "%7Bbad-json%7D"),
  "malformed DCQL JSON is rejected",
);

console.log("OID4VP request URI contract checks passed (6 assertions).");
