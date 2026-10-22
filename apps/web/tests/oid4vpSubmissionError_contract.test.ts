import {
  getOid4vpSubmissionErrorMessage,
  isFetchNetworkFailure,
} from "../src/utils/oid4vpSubmissionError.ts";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

assert(isFetchNetworkFailure(new TypeError("Failed to fetch")), "browser fetch failures are recognized");
assert(isFetchNetworkFailure(new TypeError("NetworkError when attempting to fetch resource.")), "browser network errors are recognized");
assert(!isFetchNetworkFailure(new Error("HTTP 409: Session already consumed")), "server responses are not treated as network failures");

assert(
  getOid4vpSubmissionErrorMessage(new TypeError("Failed to fetch"), "consent").includes("No presentation was created or sent"),
  "consent failure explains that presentation creation did not run",
);
assert(
  getOid4vpSubmissionErrorMessage(new TypeError("Failed to fetch"), "presentation").includes("Consent may have been recorded"),
  "presentation failure acknowledges consent may already be recorded",
);
assert(
  getOid4vpSubmissionErrorMessage(new TypeError("Failed to fetch"), "direct-post").includes("same prepared presentation"),
  "Direct Post failure directs retry to reuse the prepared presentation",
);
assert(
  getOid4vpSubmissionErrorMessage(new Error("HTTP 409: Session already consumed"), "direct-post") === "HTTP 409: Session already consumed",
  "authoritative server errors remain visible",
);

console.log("OID4VP submission recovery contract checks passed (7 assertions).");
