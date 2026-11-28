import { test } from "node:test";
import assert from "node:assert/strict";
import { classifyScanInput } from "../src/utils/scanInput.ts";

const ORIGIN = "https://wallet.example.test";
const HANDLE = "session_abcdefghijklmnopqrstuvwx";

test("the old card QR value is explained, not looked up", () => {
  const result = classifyScanInput("urn:uuid:df37d5d8-8ab1-45cd-a43b-ab984a35fabf", ORIGIN);
  assert.equal(result.kind, "rejected");
  assert.match(result.kind === "rejected" ? result.reason : "", /credential identifier/);
});

test("a DID is not a request", () => {
  assert.equal(classifyScanInput("did:key:z6Mkabc", ORIGIN).kind, "rejected");
});

test("the verifier handoff link opens the request", () => {
  assert.deepEqual(classifyScanInput(`${ORIGIN}/wallet/present?request=${HANDLE}`, ORIGIN), { kind: "handoff", request: HANDLE });
});

test("a handoff link for another site is refused", () => {
  assert.equal(classifyScanInput(`https://evil.example/wallet/present?request=${HANDLE}`, ORIGIN).kind, "rejected");
});

test("a malformed handle is refused", () => {
  assert.equal(classifyScanInput(`${ORIGIN}/wallet/present?request=../../admin`, ORIGIN).kind, "rejected");
});

for (const bad of ["javascript:alert(1)", "data:text/html,x", "file:///etc/passwd", "intent://x#Intent;end"]) {
  test(`unsafe scheme is refused: ${bad.split(":")[0]}`, () => {
    assert.equal(classifyScanInput(bad, ORIGIN).kind, "rejected");
  });
}

test("protocol links keep their own parsers", () => {
  assert.equal(classifyScanInput("openid4vp://?client_id=x", ORIGIN).kind, "oid4vp");
  assert.equal(classifyScanInput("openid-credential-offer://?credential_offer=x", ORIGIN).kind, "offer");
});

test("an oversized value is refused", () => {
  assert.equal(classifyScanInput(`${ORIGIN}/?${"a".repeat(9000)}`, ORIGIN).kind, "rejected");
});
