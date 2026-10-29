import { apiRequest, assertShape, isApiError } from "../lib/http.ts";

export type RecoveryState =
  | "PENDING_APPROVALS"
  | "QUORUM_REACHED"
  | "WAITING_TIMELOCK"
  | "READY_FOR_EXECUTION"
  | "EXECUTING"
  | "COMPLETED"
  | "REJECTED"
  | "CANCELLED"
  | "EXPIRED"
  | "FAILED"
  | "RECONCILIATION_REQUIRED"
  | "UNKNOWN";

export const ACTIVE_RECOVERY_STATES: RecoveryState[] = [
  "PENDING_APPROVALS",
  "QUORUM_REACHED",
  "WAITING_TIMELOCK",
  "READY_FOR_EXECUTION",
  "EXECUTING",
];

export type RecoveryReason = "ACCOUNT_COMPROMISE" | "LOST_ACCESS" | "DEVICE_LOSS" | "KEY_LOSS";

export interface RecoveryPolicy {
  walletId: string;
  minimumApprovals: number;
  maximumGuardians: number;
  approvalWindowSeconds: number;
  timeLockSeconds: number;
  recoveryExpirationSeconds: number;
  maximumAttempts: number;
  cooldownSeconds: number;
  allowCancellation: boolean;
  allowSelfGuardian?: boolean;
  version?: number;
}

export interface Guardian {
  guardianId: string;
  ownerUserId: string;
  walletId: string;
  guardianUserId: string;
  guardianDid: string;
  displayName: string;
  verificationMethod: string;
  status: "ACTIVE" | "SUSPENDED" | "REVOKED" | "REMOVED" | "UNKNOWN";
  createdAt: string;
}

export interface RecoveryRequest {
  requestId: string;
  sessionId: string;
  ownerUserId: string;
  walletId: string;
  reason: string;
  status: RecoveryState;
  challenge: string;
  approvalsCount: number | null;
  rejectionsCount: number | null;
  requiredCount: number | null;
  guardianCount: number | null;
  createdAt: string;
  approvalExpiresAt: string;
  expiresAt: string;
  timelockExpiresAt: string | null;
  failureCode: string | null;
  /** Recovery is not anchored on-chain in this release; never invented. */
  txHash: null;
  result: {
    predecessorKeyId: string;
    successorKeyId: string;
    predecessorDid: string;
    successorDid: string;
    completedAt: string;
  } | null;
}

export function normalizeRecoveryState(value: unknown): RecoveryState {
  const known: RecoveryState[] = [
    "PENDING_APPROVALS", "QUORUM_REACHED", "WAITING_TIMELOCK", "READY_FOR_EXECUTION", "EXECUTING",
    "COMPLETED", "REJECTED", "CANCELLED", "EXPIRED", "FAILED", "RECONCILIATION_REQUIRED",
  ];
  return typeof value === "string" && (known as string[]).includes(value) ? value as RecoveryState : "UNKNOWN";
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export function mapRecoveryRequest(value: unknown): RecoveryRequest {
  const raw = (value ?? {}) as Record<string, unknown>;
  assertShape(typeof raw.requestId === "string" && typeof raw.walletId === "string", "recovery request");
  const result = raw.result && typeof raw.result === "object" ? raw.result as Record<string, unknown> : null;
  return {
    requestId: raw.requestId as string,
    sessionId: str(raw.sessionId),
    ownerUserId: str(raw.ownerUserId),
    walletId: raw.walletId as string,
    reason: str(raw.reason, "UNSPECIFIED"),
    status: normalizeRecoveryState(raw.state ?? raw.status),
    challenge: str(raw.challenge),
    approvalsCount: num(raw.approvalCount ?? raw.approvalsCount),
    rejectionsCount: num(raw.rejectionCount),
    requiredCount: num(raw.minimumApprovals ?? raw.requiredCount),
    guardianCount: num(raw.guardianCount),
    createdAt: str(raw.createdAt),
    approvalExpiresAt: str(raw.approvalExpiresAt),
    expiresAt: str(raw.expiresAt),
    timelockExpiresAt: typeof raw.executableAfter === "string" ? raw.executableAfter : null,
    failureCode: typeof raw.failureCode === "string" ? raw.failureCode : null,
    txHash: null,
    result: result
      ? {
          predecessorKeyId: str(result.predecessorKeyId),
          successorKeyId: str(result.successorKeyId),
          predecessorDid: str(result.predecessorDid),
          successorDid: str(result.successorDid),
          completedAt: str(result.completedAt),
        }
      : null,
  };
}

function mapGuardian(value: unknown): Guardian {
  const raw = (value ?? {}) as Record<string, unknown>;
  assertShape(typeof raw.guardianId === "string" && typeof raw.walletId === "string", "guardian record");
  const status = str(raw.status);
  return {
    guardianId: raw.guardianId as string,
    ownerUserId: str(raw.ownerUserId),
    walletId: raw.walletId as string,
    guardianUserId: str(raw.guardianUserId),
    guardianDid: str(raw.guardianDid),
    displayName: str(raw.displayName, "Unnamed guardian"),
    verificationMethod: str(raw.verificationMethod),
    status: (["ACTIVE", "SUSPENDED", "REVOKED", "REMOVED"] as const).includes(status as "ACTIVE")
      ? status as Guardian["status"]
      : "UNKNOWN",
    createdAt: str(raw.createdAt),
  };
}

/** Guardians the user owns or is assigned to. Errors are thrown, never hidden. */
export async function fetchGuardians(walletId?: string): Promise<Guardian[]> {
  const query = walletId ? `?walletId=${encodeURIComponent(walletId)}` : "";
  const body = await apiRequest<{ items?: unknown }>(`/api/v1/recovery/guardians${query}`);
  assertShape(Array.isArray(body?.items), "guardian list");
  return (body.items as unknown[]).map(mapGuardian);
}

/** Default verification method for a did:key guardian (did:key:z…#z…). */
export function defaultVerificationMethod(did: string): string {
  if (did.startsWith("did:key:")) {
    const fragment = did.slice("did:key:".length);
    return `${did}#${fragment}`;
  }
  return `${did}#key-1`;
}

export async function addGuardian(payload: {
  walletId: string;
  guardianUserId: string;
  guardianDid: string;
  displayName: string;
  verificationMethod?: string;
}): Promise<Guardian> {
  return mapGuardian(await apiRequest<unknown>("/api/v1/recovery/guardians", {
    method: "POST",
    body: {
      walletId: payload.walletId,
      guardianUserId: payload.guardianUserId.trim(),
      guardianDid: payload.guardianDid.trim(),
      displayName: payload.displayName.trim(),
      verificationMethod: payload.verificationMethod?.trim() || defaultVerificationMethod(payload.guardianDid.trim()),
    },
  }));
}

export async function removeGuardian(guardianId: string): Promise<Guardian> {
  return mapGuardian(await apiRequest<unknown>(`/api/v1/recovery/guardians/${encodeURIComponent(guardianId)}`, {
    method: "DELETE",
  }));
}

function isRecoveryPolicyForWallet(value: unknown, walletId: string): value is RecoveryPolicy {
  if (typeof value !== "object" || value === null) return false;
  const policy = value as Partial<RecoveryPolicy>;
  const atLeast = (candidate: unknown, minimum: number): candidate is number =>
    typeof candidate === "number" && Number.isInteger(candidate) && candidate >= minimum;
  return policy.walletId === walletId
    && atLeast(policy.minimumApprovals, 1)
    && atLeast(policy.maximumGuardians, policy.minimumApprovals)
    && policy.maximumGuardians <= 32
    && atLeast(policy.approvalWindowSeconds, 60)
    && atLeast(policy.timeLockSeconds, 0)
    && policy.timeLockSeconds <= 30 * 24 * 60 * 60
    && atLeast(policy.recoveryExpirationSeconds, policy.approvalWindowSeconds + policy.timeLockSeconds)
    && atLeast(policy.maximumAttempts, 1)
    && policy.maximumAttempts <= 20
    && atLeast(policy.cooldownSeconds, 0)
    && typeof policy.allowCancellation === "boolean";
}

/**
 * For screens: null means "no policy exists" (HTTP 404). Unavailability and
 * invalid policies throw, so they are never shown as "not configured".
 */
export async function fetchRecoveryPolicyStrict(walletId: string): Promise<RecoveryPolicy | null> {
  let body: unknown;
  try {
    body = await apiRequest<unknown>(`/api/v1/recovery/policy?walletId=${encodeURIComponent(walletId)}`);
  } catch (error) {
    if (isApiError(error) && error.kind === "not_found") return null;
    throw error;
  }
  assertShape(isRecoveryPolicyForWallet(body, walletId), "recovery policy");
  return body as RecoveryPolicy;
}

/**
 * Existing contract (tests/recoveryApi_contract): any failure, a policy for a
 * different wallet or an invalid quorum yields null — never a default policy.
 */
export async function fetchRecoveryPolicy(walletId: string): Promise<RecoveryPolicy | null> {
  try {
    return await fetchRecoveryPolicyStrict(walletId);
  } catch {
    return null;
  }
}

export async function upsertRecoveryPolicy(policy: RecoveryPolicy): Promise<RecoveryPolicy> {
  const body = await apiRequest<RecoveryPolicy>("/api/v1/recovery/policy", {
    method: "PUT",
    body: {
      walletId: policy.walletId,
      minimumApprovals: policy.minimumApprovals,
      maximumGuardians: policy.maximumGuardians,
      approvalWindowSeconds: policy.approvalWindowSeconds,
      timeLockSeconds: policy.timeLockSeconds,
      recoveryExpirationSeconds: policy.recoveryExpirationSeconds,
      maximumAttempts: policy.maximumAttempts,
      cooldownSeconds: policy.cooldownSeconds,
      allowCancellation: policy.allowCancellation,
    },
  });
  assertShape(body && body.walletId === policy.walletId, "recovery policy");
  return body;
}

export function canInitiateRecovery(
  walletId: string | null,
  policy: RecoveryPolicy | null,
  activeGuardianCount: number,
  hasActiveRequest: boolean,
): boolean {
  return !hasActiveRequest
    && Boolean(walletId && policy && policy.walletId === walletId)
    && Number.isInteger(activeGuardianCount)
    && activeGuardianCount >= (policy?.minimumApprovals ?? Number.POSITIVE_INFINITY)
    && activeGuardianCount <= (policy?.maximumGuardians ?? -1);
}

export async function fetchRecoveryRequests(limit = 50): Promise<RecoveryRequest[]> {
  const body = await apiRequest<{ items?: unknown }>(`/api/v1/recovery/requests?limit=${limit}`);
  assertShape(Array.isArray(body?.items), "recovery request list");
  return (body.items as unknown[]).map(mapRecoveryRequest);
}

export async function fetchRecoveryRequestById(requestId: string): Promise<RecoveryRequest> {
  return mapRecoveryRequest(await apiRequest<unknown>(`/api/v1/recovery/requests/${encodeURIComponent(requestId)}`));
}

export async function initiateRecoveryRequest(params: { walletId: string; reason: RecoveryReason }): Promise<RecoveryRequest> {
  return mapRecoveryRequest(await apiRequest<unknown>("/api/v1/recovery/requests", {
    method: "POST",
    body: { walletId: params.walletId, reason: params.reason },
  }));
}

export async function cancelRecoveryRequest(requestId: string): Promise<RecoveryRequest> {
  return mapRecoveryRequest(await apiRequest<unknown>(`/api/v1/recovery/requests/${encodeURIComponent(requestId)}/cancel`, {
    method: "POST",
  }));
}

async function guardianDecisionProof(
  request: RecoveryRequest,
  guardian: Guardian,
  decision: "APPROVE" | "REJECT",
): Promise<string> {
  if (!request.sessionId || !request.challenge || !guardian.guardianDid) {
    throw new Error("The recovery session, server challenge and assigned guardian DID are required.");
  }
  const body = await apiRequest<{ proof?: unknown; guardianDid?: unknown }>(
    "/api/v1/identity/wallets/guardian-recovery-proof",
    {
      method: "POST",
      body: {
        requestId: request.requestId,
        sessionId: request.sessionId,
        guardianId: guardian.guardianId,
        walletId: request.walletId,
        guardianDid: guardian.guardianDid,
        challenge: request.challenge,
        decision,
      },
    },
  );
  assertShape(typeof body?.proof === "string" && body.guardianDid === guardian.guardianDid, "guardian decision proof");
  return body.proof as string;
}

/**
 * Two server calls: the Identity Service signs the challenge-bound decision
 * with the guardian's *server-managed* wallet key, then the Recovery Service
 * verifies that signature against the registered guardian DID.
 */
export async function decideRecoveryRequest(
  request: RecoveryRequest,
  guardian: Guardian,
  decision: "APPROVE" | "REJECT",
): Promise<RecoveryRequest> {
  const proof = await guardianDecisionProof(request, guardian, decision);
  const body = await apiRequest<{ recovery?: unknown }>(
    `/api/v1/recovery/requests/${encodeURIComponent(request.requestId)}/${decision === "APPROVE" ? "approve" : "reject"}`,
    { method: "POST", body: { guardianId: guardian.guardianId, challenge: request.challenge, proof } },
  );
  return mapRecoveryRequest(body?.recovery);
}

/** Existing contract wrappers used by tests/recoveryApi_contract. */
export async function approveRecoveryPetition(
  request: RecoveryRequest,
  guardianId: string,
  guardianDid: string,
): Promise<{ success: true; request: RecoveryRequest }> {
  const updated = await decideRecoveryRequest(request, { guardianId, guardianDid } as Guardian, "APPROVE");
  return { success: true, request: updated };
}

export async function rejectRecoveryPetition(
  request: RecoveryRequest,
  guardianId: string,
  guardianDid: string,
): Promise<{ success: true; request: RecoveryRequest }> {
  const updated = await decideRecoveryRequest(request, { guardianId, guardianDid } as Guardian, "REJECT");
  return { success: true, request: updated };
}
