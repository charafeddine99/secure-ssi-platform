/**
 * WP-01 GAP-07 Test Suite: Frontend Fail-Closed Verification
 * 
 * Verifies that:
 * 1. Network failure MUST NOT render a successful verification state.
 * 2. HTTP 4xx errors return status: "UNAVAILABLE" or "REJECTED" with verified: false.
 * 3. HTTP 5xx errors return status: "UNAVAILABLE" or "ERROR" with verified: false.
 * 4. Network timeout / connection drops return status: "UNAVAILABLE" with verified: false.
 * 5. Malformed API response returns verified: false.
 * 6. Valid positive verification response returns status: "VERIFIED" with verified: true.
 */

import assert from "node:assert/strict";

// We mock globalThis.localStorage for Node environment
const mockStorage: Record<string, string> = {
  token: "mock-test-jwt-token"
};

globalThis.localStorage = {
  getItem: (key: string) => mockStorage[key] || null,
  setItem: (key: string, val: string) => { mockStorage[key] = val; },
  removeItem: (key: string) => { delete mockStorage[key]; },
  clear: () => { Object.keys(mockStorage).forEach(k => delete mockStorage[k]); },
  length: 0,
  key: () => null,
};

// Import verifyPresentation from api.ts
import { verifyPresentation } from "../src/services/api.ts";

async function runTests() {
  console.log("Starting WP-01 GAP-07 Frontend Fail-Closed Tests...\n");

  const originalFetch = globalThis.fetch;

  try {
    // ------------------------------------------------------------------------
    // 1. Network / Transport Connection Failure (Network drop, DNS failure)
    // ------------------------------------------------------------------------
    {
      console.log("Test 1: Network / Transport failure must NOT return verified: true");
      globalThis.fetch = async () => {
        throw new TypeError("Failed to fetch: NetworkError when attempting to fetch resource.");
      };

      const result = await verifyPresentation({
        session_id: "test-session-1",
        vp_token: { type: ["VerifiablePresentation"] },
      });

      assert.strictEqual(result.verified, false, "verified MUST be false on network error");
      assert.strictEqual(result.status, "UNAVAILABLE", "status MUST be UNAVAILABLE on network error");
      assert.ok(result.errors && result.errors.length > 0, "errors MUST be populated");
      assert.match(result.errors![0], /NetworkError|Failed to fetch|Bağlantı hatası/i);
      console.log("  ✓ PASSED: Network failure returned verified=false, status=UNAVAILABLE\n");
    }

    // ------------------------------------------------------------------------
    // 2. HTTP 500 Internal Server Error
    // ------------------------------------------------------------------------
    {
      console.log("Test 2: HTTP 500 Server Error must NOT return verified: true");
      globalThis.fetch = async () => {
        return new Response(JSON.stringify({ detail: "Internal database connection failure" }), {
          status: 500,
          statusText: "Internal Server Error",
          headers: { "Content-Type": "application/json" }
        });
      };

      const result = await verifyPresentation({
        session_id: "test-session-2",
        vp_token: { type: ["VerifiablePresentation"] },
      });

      assert.strictEqual(result.verified, false, "verified MUST be false on HTTP 500");
      assert.ok(result.status === "UNAVAILABLE" || result.status === "ERROR", "status MUST be UNAVAILABLE or ERROR");
      assert.ok(result.errors && result.errors.length > 0);
      console.log("  ✓ PASSED: HTTP 500 returned verified=false, status=" + result.status + "\n");
    }

    // ------------------------------------------------------------------------
    // 3. HTTP 400 Bad Request / Validation Failure
    // ------------------------------------------------------------------------
    {
      console.log("Test 3: HTTP 400 Bad Request must NOT return verified: true");
      globalThis.fetch = async () => {
        return new Response(JSON.stringify({ detail: "Invalid presentation schema" }), {
          status: 400,
          statusText: "Bad Request",
          headers: { "Content-Type": "application/json" }
        });
      };

      const result = await verifyPresentation({
        session_id: "test-session-3",
        vp_token: { type: ["VerifiablePresentation"] },
      });

      assert.strictEqual(result.verified, false, "verified MUST be false on HTTP 400");
      assert.strictEqual(result.status, "REJECTED", "status MUST be REJECTED on client verification error");
      assert.ok(result.errors && result.errors.length > 0);
      console.log("  ✓ PASSED: HTTP 400 returned verified=false, status=REJECTED\n");
    }

    // ------------------------------------------------------------------------
    // 4. Malformed JSON Response from Server
    // ------------------------------------------------------------------------
    {
      console.log("Test 4: Malformed non-JSON response must NOT return verified: true");
      globalThis.fetch = async () => {
        return new Response("<html><body>502 Bad Gateway</body></html>", {
          status: 502,
          statusText: "Bad Gateway",
          headers: { "Content-Type": "text/html" }
        });
      };

      const result = await verifyPresentation({
        session_id: "test-session-4",
        vp_token: { type: ["VerifiablePresentation"] },
      });

      assert.strictEqual(result.verified, false, "verified MUST be false on malformed/gateway error");
      assert.ok(result.status === "UNAVAILABLE" || result.status === "ERROR");
      console.log("  ✓ PASSED: Malformed gateway error returned verified=false\n");
    }

    // ------------------------------------------------------------------------
    // 5. Positive Golden Path Verification
    // ------------------------------------------------------------------------
    {
      console.log("Test 5: Authoritative success from backend must return verified: true");
      globalThis.fetch = async () => {
        return new Response(JSON.stringify({
          sessionId: "test-session-5",
          result: {
            credentialValid: true,
            issuerTrusted: true,
            signatureValid: true,
            holderBindingValid: true,
            expirationValid: true,
            revocationStatusClear: true,
            challengeValid: true,
            aiRiskLevel: "LOW",
            aiRiskScore: 10,
            blockchainAnchored: true,
            finalPolicyResult: "ACCEPTED",
            details: {
              evaluations: {
                cryptographic: "VALID",
                revocation: "VALID",
                trust_registry: "VALID",
                schema: "VALID",
                policy: "LOW",
              }
            }
          },
          disclosedClaims: { degree: "MSc Computer Science" }
        }), {
          status: 200,
          statusText: "OK",
          headers: { "Content-Type": "application/json" }
        });
      };

      const result = await verifyPresentation({
        session_id: "test-session-5",
        vp_token: { type: ["VerifiablePresentation"] },
      });

      assert.strictEqual(result.verified, true, "verified MUST be true when authoritative backend returns ACCEPTED");
      assert.strictEqual(result.status, "VERIFIED", "status MUST be VERIFIED");
      assert.strictEqual(result.signature_valid, true);
      assert.strictEqual(result.challenge_valid, true);
      assert.strictEqual(result.claims?.degree, "MSc Computer Science");
      console.log("  ✓ PASSED: Authoritative ACCEPTED returned verified=true, status=VERIFIED\n");
    }

    console.log("=================================================");
    console.log("ALL GAP-07 FRONTEND FAIL-CLOSED TESTS PASSED!");
    console.log("=================================================");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

runTests().catch((err) => {
  console.error("TEST FAILED:", err);
  process.exit(1);
});
