import { test } from "node:test";
import assert from "node:assert/strict";
import { cardStatus } from "../src/utils/cardStatus.ts";

const NOW = Date.parse("2026-11-07T12:00:00Z");
const FUTURE = "2027-11-07T00:00:00Z";
const PAST = "2026-01-01T00:00:00Z";
const ok = (status: "ACTIVE" | "SUSPENDED" | "REVOKED" | "EXPIRED" | "UNKNOWN") => ({ status: "success" as const, data: { status } });

test("an active credential from the issuer is valid and keeps its colour", () => {
  assert.deepEqual(cardStatus(FUTURE, ok("ACTIVE"), NOW), { key: "valid", text: "Active", inactive: false, blocked: null });
});

test("past validUntil shows Expired even if the issuer still says active", () => {
  assert.deepEqual(cardStatus(PAST, ok("ACTIVE"), NOW), { key: "expired", text: "Expired", inactive: true, blocked: "This credential has expired." });
});

test("past validUntil shows Expired while the check is still running", () => {
  assert.equal(cardStatus(PAST, { status: "loading" }, NOW).key, "expired");
});

test("while checking, the card says so and is not dimmed", () => {
  assert.deepEqual(cardStatus(FUTURE, { status: "loading" }, NOW), { key: "checking", text: "Checking…", inactive: false, blocked: null });
});

test("a failed check is Unknown, never Active", () => {
  assert.deepEqual(cardStatus(FUTURE, { status: "error" }, NOW), { key: "unknown", text: "Unknown", inactive: true, blocked: null });
});

for (const [status, text] of [["REVOKED", "Revoked"], ["SUSPENDED", "Suspended"], ["EXPIRED", "Expired"], ["UNKNOWN", "Unknown"]] as const) {
  test(`issuer answer ${status} is shown as ${text} and dimmed`, () => {
    const result = cardStatus(FUTURE, ok(status), NOW);
    assert.equal(result.text, text);
    assert.equal(result.inactive, true);
  });
}

test("no validUntil means no date expiry", () => {
  assert.equal(cardStatus(null, ok("ACTIVE"), NOW).key, "valid");
});

test("a credential before validFrom is Not yet valid and cannot be presented", () => {
  const later = new Date(NOW + 86_400_000).toISOString();
  assert.deepEqual(cardStatus(FUTURE, ok("ACTIVE"), NOW, later), { key: "not-yet-valid", text: "Not yet valid", inactive: true, blocked: "This credential is not valid yet." });
});

test("revoked and suspended block Present; Active and Unknown do not", () => {
  assert.equal(cardStatus(FUTURE, ok("REVOKED"), NOW).blocked, "The issuer revoked this credential.");
  assert.equal(cardStatus(FUTURE, ok("SUSPENDED"), NOW).blocked, "The issuer suspended this credential.");
  assert.equal(cardStatus(FUTURE, ok("ACTIVE"), NOW).blocked, null);
  assert.equal(cardStatus(FUTURE, { status: "error" }, NOW).blocked, null);
});
