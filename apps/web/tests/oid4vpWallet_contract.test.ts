import {
  createWalletOid4vpPresentation,
  evaluateOid4vpSession,
  recordWalletOid4vpConsent,
} from "../src/services/api.ts";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

async function runTests(): Promise<void> {
  const previousFetch = globalThis.fetch;
  const previousLocalStorage = globalThis.localStorage;
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.localStorage = {
    getItem: (key: string) => key === "ssi_session_active" ? "1" : null,
    setItem: () => undefined,
    removeItem: () => undefined,
    clear: () => undefined,
    key: () => null,
    length: 0,
  };
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    const body = String(init?.body || "{}");
    if (String(input).endsWith("/evaluate-dcql")) {
      return new Response(JSON.stringify({
        isSatisfied: true,
        matchedCredentials: [{ queryId: "credential_1", credentialId: "urn:vc:one", matchedClaims: {} }],
        details: { selectedQueryIds: ["credential_1"] },
      }), { status: 200 });
    }
    if (String(input).endsWith("/wallet-consent")) {
      return new Response(JSON.stringify({ sessionId: "session_12345678", action: JSON.parse(body).action }), { status: 200 });
    }
    if (String(input).endsWith("/wallet-presentation")) {
      return new Response(JSON.stringify({ sessionId: "session_12345678", vpToken: { type: ["VerifiablePresentation"] } }), { status: 200 });
    }
    return new Response("unexpected route", { status: 404 });
  }) as typeof globalThis.fetch;

  try {
    const evaluation = await evaluateOid4vpSession("session_12345678", [{ id: "urn:vc:one" }]);
    assert(evaluation.isSatisfied && evaluation.matchedCredentials[0]?.credentialId === "urn:vc:one", "DCQL result is returned from the server");
    const candidateBody = JSON.parse(String(calls[0]?.init?.body)) as Record<string, unknown>;
    assert(Array.isArray(candidateBody.candidateCredentials), "wallet credential documents are sent for DCQL evaluation");

    await recordWalletOid4vpConsent({
      sessionId: "session_12345678",
      walletId: "wallet_1234567890123456",
      holderDid: "did:key:holder",
      action: "APPROVE",
      approvedCredentials: ["urn:vc:one"],
      approvedClaims: { degree: "Computer Engineering" },
    });
    const consentCall = calls[1];
    const consentPayload = JSON.parse(String(consentCall?.init?.body)) as Record<string, unknown>;
    assert(consentCall?.url.endsWith("/wallet-consent"), "consent uses the wallet-bound endpoint");
    assert(consentCall?.init?.credentials === "include" && !new Headers(consentCall?.init?.headers).has("Authorization"), "consent uses the HttpOnly session cookie, not a JS-held token");
    assert(new Headers(consentCall?.init?.headers).get("X-SSI-Client") === "web", "consent sends the CSRF client header");
    assert(consentPayload.walletId === "wallet_1234567890123456", "consent binds the selected wallet");

    await createWalletOid4vpPresentation({
      sessionId: "session_12345678",
      walletId: "wallet_1234567890123456",
      credentialIds: ["urn:vc:one"],
      disclosedClaims: { degree: "Computer Engineering" },
    });
    const presentationCall = calls[2];
    const presentationPayload = JSON.parse(String(presentationCall?.init?.body)) as Record<string, unknown>;
    assert(presentationCall?.url.endsWith("/wallet-presentation"), "presentation uses the wallet-bound endpoint");
    assert(presentationCall?.init?.credentials === "include", "presentation uses the HttpOnly session cookie");
    assert(JSON.stringify(presentationPayload.credentialIds) === JSON.stringify(["urn:vc:one"]), "presentation binds selected credential IDs");

    globalThis.localStorage.getItem = () => null;
    const callsBeforeMissingToken = calls.length;
    let missingTokenFailedClosed = false;
    try {
      await recordWalletOid4vpConsent({ sessionId: "session_12345678", walletId: "wallet_1234567890123456", holderDid: "did:key:holder", action: "REJECT" });
    } catch {
      missingTokenFailedClosed = true;
    }
    assert(missingTokenFailedClosed && calls.length === callsBeforeMissingToken, "a signed-out wallet fails before sending a consent request");

    console.log("OID4VP wallet API contract checks passed (10 assertions).");
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.localStorage = previousLocalStorage;
  }
}

void runTests();
