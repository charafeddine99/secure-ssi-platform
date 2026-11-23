import { didKeyFromPublicKey } from "../src/lib/guardianDeviceKey.ts";
import {
  decideRecoveryRequest,
  canInitiateRecovery,
  fetchRecoveryPolicy,
  mapRecoveryRequest,
  normalizeRecoveryState,
} from "../src/services/api.ts";

let assertionCount = 0;

function equal(actual: unknown, expected: unknown, message: string): void {
  assertionCount += 1;
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, received ${String(actual)}`);
  }
}

function ok(value: unknown, message: string): asserts value {
  assertionCount += 1;
  if (!value) throw new Error(message);
}

const requestDocument = {
  requestId: "recovery_test_1234567890123456",
  sessionId: "session_test_1234567890123456",
  ownerUserId: "user_owner",
  walletId: "wallet_test_1234567890123456",
  state: "PENDING_APPROVALS",
  challenge: "server-issued-challenge-value-1234567890",
  reason: "LOST_ACCESS",
  approvalCount: 1,
  rejectionCount: 0,
  minimumApprovals: 3,
  guardianCount: 5,
  createdAt: "2026-10-13T10:00:00Z",
  expiresAt: "2026-10-14T10:00:00Z",
  executableAfter: null,
  result: null,
};

async function runTests(): Promise<void> {
  const mapped = mapRecoveryRequest(requestDocument);
  equal(mapped.status, "PENDING_APPROVALS", "Backend state is preserved");
  equal(mapped.approvalsCount, 1, "Backend approvalCount is mapped");
  equal(mapped.requiredCount, 3, "Backend minimumApprovals is mapped");
  equal(mapped.challenge, requestDocument.challenge, "Server challenge is available to the decision flow");
  equal(mapped.txHash, null, "No blockchain transaction is invented");
  equal(normalizeRecoveryState("unrecognized"), "UNKNOWN", "Unknown states fail to UNKNOWN");

  const previousFetch = globalThis.fetch;
  const previousLocalStorage = globalThis.localStorage;
  let capturedBody = "";
  let responseStatus = 200;
  let responseDocument: Record<string, unknown> = { recovery: requestDocument };
  let capturedRecoveryUrl = "";
  const recoveryPolicy = {
    walletId: "wallet_policy_1234567890123456",
    minimumApprovals: 2,
    maximumGuardians: 3,
    approvalWindowSeconds: 3600,
    timeLockSeconds: 60,
    recoveryExpirationSeconds: 7200,
    maximumAttempts: 3,
    cooldownSeconds: 300,
    allowCancellation: true,
  };
  globalThis.localStorage = {
    getItem: (key: string) => key === "ssi_session_active" ? "1" : null,
    setItem: () => undefined,
    removeItem: () => undefined,
    clear: () => undefined,
    key: () => null,
    length: 0,
  };
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("guardian-recovery-proof")) {
      throw new Error("The web app must never ask the server to sign for a Guardian.");
    }
    capturedRecoveryUrl = url;
    capturedBody = String(init?.body ?? "");
    return new Response(JSON.stringify(responseDocument), {
      status: responseStatus,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof globalThis.fetch;

  try {
    responseDocument = recoveryPolicy;
    const loadedPolicy = await fetchRecoveryPolicy(recoveryPolicy.walletId);
    equal(loadedPolicy?.minimumApprovals, 2, "Policy threshold comes from the backend response");
    equal(loadedPolicy?.maximumGuardians, 3, "Guardian limit comes from the backend response");
    equal(canInitiateRecovery(recoveryPolicy.walletId, loadedPolicy, 2, false), true, "A matching policy with enough active Guardians permits a request");
    equal(canInitiateRecovery(recoveryPolicy.walletId, loadedPolicy, 1, false), false, "A request is blocked below the backend quorum");
    equal(canInitiateRecovery("another_wallet_123456789012", loadedPolicy, 2, false), false, "A policy cannot authorize a different wallet");
    equal(canInitiateRecovery(recoveryPolicy.walletId, loadedPolicy, 2, true), false, "An active request blocks another request");
    equal(canInitiateRecovery(recoveryPolicy.walletId, loadedPolicy, 4, false), false, "A guardian count above the backend maximum fails closed");

    responseDocument = { ...recoveryPolicy, walletId: "different_wallet_123456789012" };
    equal(await fetchRecoveryPolicy(recoveryPolicy.walletId), null, "A policy for a different wallet is rejected");
    responseDocument = { ...recoveryPolicy, minimumApprovals: 4, maximumGuardians: 3 };
    equal(await fetchRecoveryPolicy(recoveryPolicy.walletId), null, "An invalid quorum policy is rejected");
    responseStatus = 503;
    equal(await fetchRecoveryPolicy(recoveryPolicy.walletId), null, "An unavailable policy does not become a default policy");

    responseStatus = 200;
    responseDocument = { recovery: requestDocument };
    const pair = await crypto.subtle.generateKey("Ed25519", false, ["sign", "verify"]) as CryptoKeyPair;
    const raw = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
    const identity = didKeyFromPublicKey(raw);
    const deviceKey = {
      ...identity,
      sign: async (data: Uint8Array) => new Uint8Array(await crypto.subtle.sign("Ed25519", pair.privateKey, data as BufferSource)),
    };
    const assigned = { guardianId: "guardian_test_1234567890123456", guardianDid: identity.did } as Guardian;
    const signedRequest = { ...mapped, policyHash: "a".repeat(64) };
    await decideRecoveryRequest(signedRequest, assigned, "APPROVE", deviceKey);
    equal(capturedRecoveryUrl.endsWith(`/recovery/requests/${requestDocument.requestId}/approve`), true, "Approval uses the backend request ID");
    const payload = JSON.parse(capturedBody) as Record<string, unknown>;
    equal(payload.challenge, requestDocument.challenge, "Approval sends the server challenge");
    equal(payload.guardianId, "guardian_test_1234567890123456", "Approval sends the selected assignment");
    const [header, claims, signature] = String(payload.proof).split(".");
    const decoded = JSON.parse(Buffer.from(claims, "base64url").toString("utf8")) as Record<string, unknown>;
    equal(JSON.parse(Buffer.from(header, "base64url").toString("utf8")).typ, "guardian-recovery+jwt", "The proof is a Guardian decision token");
    equal(decoded.policyHash, "a".repeat(64), "The proof covers the policy snapshot");
    equal(decoded.iss, identity.did, "The proof is issued by the Guardian's own key");
    ok(
      await crypto.subtle.verify("Ed25519", pair.publicKey, Buffer.from(signature, "base64url"), new TextEncoder().encode(`${header}.${claims}`)),
      "The signature was made locally and verifies against the device key",
    );

    responseStatus = 403;
    responseDocument = { message: "Guardian assignment is not authorized." };
    let rejected = false;
    try {
      await decideRecoveryRequest(signedRequest, assigned, "REJECT", deviceKey);
    } catch (error: unknown) {
      rejected = error instanceof Error && error.message === "Guardian assignment is not authorized.";
    }
    ok(rejected, "HTTP rejection is surfaced to the caller");
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.localStorage = previousLocalStorage;
  }
  console.log(`Recovery API contract checks passed (${assertionCount} assertions).`);
}

void runTests();
