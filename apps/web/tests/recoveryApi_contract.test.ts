import {
  approveRecoveryPetition,
  canInitiateRecovery,
  fetchRecoveryPolicy,
  mapRecoveryRequest,
  normalizeRecoveryState,
  rejectRecoveryPetition,
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
    if (url.includes("/identity/wallets/guardian-recovery-proof")) {
      return new Response(JSON.stringify({ guardianDid: "did:key:zGuardianProofKey", proof: "signed-guardian-proof" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
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
    const decision = await approveRecoveryPetition(
      mapped,
      "guardian_test_1234567890123456",
      "did:key:zGuardianProofKey",
    );
    equal(decision.success, true, "Approval success follows an HTTP success response");
    equal(capturedRecoveryUrl.endsWith(`/recovery/requests/${requestDocument.requestId}/approve`), true, "Approval uses the backend request ID");
    const payload = JSON.parse(capturedBody) as Record<string, unknown>;
    equal(payload.challenge, requestDocument.challenge, "Approval sends the server challenge");
    equal(payload.guardianId, "guardian_test_1234567890123456", "Approval sends the selected assignment");
    equal(payload.proof, "signed-guardian-proof", "Approval sends the proof returned by the Identity Service signer");

    responseStatus = 403;
    responseDocument = { message: "Guardian assignment is not authorized." };
    let rejected = false;
    try {
      await rejectRecoveryPetition(
        mapped,
        "guardian_test_1234567890123456",
        "did:key:zGuardianProofKey",
      );
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
