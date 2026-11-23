import { apiRequest, assertShape, isApiError } from "../lib/http.ts";
import { stepUpHeaders } from "./stepUp.ts";
import { signGuardianJwt, type GuardianDeviceKey } from "../lib/guardianDeviceKey.ts";

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
  version?: number;
  /** A weakening change waiting out its delay; the values above still apply. */
  pendingChange?: Partial<Record<string, number | boolean>> | null;
  pendingEffectiveAt?: string | null;
}

export interface Guardian {
  guardianId: string;
  ownerUserId: string;
  walletId: string;
  guardianUserId: string;
  guardianDid: string;
  displayName: string;
  verificationMethod: string;
  status: "INVITED" | "PENDING_ACTIVATION" | "ACTIVE" | "SUSPENDED" | "REVOKED" | "REMOVED" | "UNKNOWN";
  createdAt: string;
  pendingStatus: string | null;
  pendingEffectiveAt: string | null;
}

export interface GuardianInvitation {
  guardianId: string;
  walletId: string;
  displayName: string;
  challenge: string;
  expiresAt: string;
  purpose: "ENROLL" | "REBIND";
}

export interface RecoveryNotification {
  notificationId: string;
  eventType: string;
  aggregateId: string;
  walletId: string;
  createdAt: string;
  readAt: string | null;
  delivery: string;
  emailStatus: string;
}

export interface RecoveryRequest {
  requestId: string;
  sessionId: string;
  ownerUserId: string;
  walletId: string;
  reason: string;
  status: RecoveryState;
  challenge: string;
  policyHash: string;
  riskLevel: string;
  riskStatus: string;
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
    policyHash: str(raw.policyHash),
    riskLevel: str(raw.riskLevel, "NOT_ASSESSED"),
    riskStatus: str(raw.riskStatus, "ON_HOLD"),
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
    status: (["INVITED", "PENDING_ACTIVATION", "ACTIVE", "SUSPENDED", "REVOKED", "REMOVED"] as const).includes(status as "ACTIVE")
      ? status as Guardian["status"]
      : "UNKNOWN",
    createdAt: str(raw.createdAt),
    pendingStatus: typeof raw.pendingStatus === "string" ? raw.pendingStatus : null,
    pendingEffectiveAt: typeof raw.pendingEffectiveAt === "string" ? raw.pendingEffectiveAt : null,
  };
}

/** Guardians the user owns or is assigned to. Errors are thrown, never hidden. */
export async function fetchGuardians(walletId?: string): Promise<Guardian[]> {
  const query = walletId ? `?walletId=${encodeURIComponent(walletId)}` : "";
  const body = await apiRequest<{ items?: unknown }>(`/api/v1/recovery/guardians${query}`);
  assertShape(Array.isArray(body?.items), "guardian list");
  return (body.items as unknown[]).map(mapGuardian);
}

/** Invites an account. It has no authority until that person accepts with their own key. */
export async function addGuardian(
  payload: { walletId: string; guardianUserId: string; displayName: string },
  stepUpToken?: string | null,
): Promise<Guardian> {
  return mapGuardian(await apiRequest<unknown>("/api/v1/recovery/guardians", {
    method: "POST",
    headers: stepUpHeaders(stepUpToken),
    body: {
      walletId: payload.walletId,
      guardianUserId: payload.guardianUserId.trim(),
      displayName: payload.displayName.trim(),
    },
  }));
}

export async function removeGuardian(guardianId: string, stepUpToken?: string | null): Promise<Guardian> {
  return mapGuardian(await apiRequest<unknown>(`/api/v1/recovery/guardians/${encodeURIComponent(guardianId)}`, {
    method: "DELETE",
    headers: stepUpHeaders(stepUpToken),
  }));
}

export async function fetchGuardianInvitations(): Promise<GuardianInvitation[]> {
  const body = await apiRequest<{ items?: unknown }>("/api/v1/recovery/guardians/invitations");
  assertShape(Array.isArray(body?.items), "guardian invitations");
  return body.items as GuardianInvitation[];
}

function bindingProof(key: GuardianDeviceKey, invitation: GuardianInvitation): Promise<string> {
  return signGuardianJwt(key, "guardian-binding+jwt", {
    sub: invitation.guardianId,
    walletId: invitation.walletId,
    challenge: invitation.challenge,
  });
}

export async function acceptGuardianInvitation(
  invitation: GuardianInvitation,
  key: GuardianDeviceKey,
  stepUpToken?: string | null,
): Promise<Guardian> {
  return mapGuardian(await apiRequest<unknown>(
    `/api/v1/recovery/guardians/${encodeURIComponent(invitation.guardianId)}/accept`,
    {
      method: "POST",
      headers: stepUpHeaders(stepUpToken),
      body: {
        guardianDid: key.did,
        verificationMethod: key.verificationMethod,
        proof: await bindingProof(key, invitation),
      },
    },
  ));
}

export async function startGuardianRebind(guardianId: string): Promise<GuardianInvitation> {
  return apiRequest<GuardianInvitation>(`/api/v1/recovery/guardians/${encodeURIComponent(guardianId)}/rebind`, { method: "POST" });
}

export async function completeGuardianRebind(
  invitation: GuardianInvitation,
  key: GuardianDeviceKey,
  stepUpToken?: string | null,
): Promise<Guardian> {
  return mapGuardian(await apiRequest<unknown>(
    `/api/v1/recovery/guardians/${encodeURIComponent(invitation.guardianId)}/rebind`,
    {
      method: "PUT",
      headers: stepUpHeaders(stepUpToken),
      body: {
        guardianDid: key.did,
        verificationMethod: key.verificationMethod,
        proof: await bindingProof(key, invitation),
      },
    },
  ));
}

export async function fetchRecoveryNotifications(): Promise<RecoveryNotification[]> {
  const body = await apiRequest<{ items?: unknown }>("/api/v1/recovery/notifications");
  assertShape(Array.isArray(body?.items), "recovery notifications");
  return body.items as RecoveryNotification[];
}

export async function markRecoveryNotificationRead(notificationId: string): Promise<void> {
  await apiRequest<unknown>(`/api/v1/recovery/notifications/${encodeURIComponent(notificationId)}/read`, { method: "POST" });
}

export async function reviewRecoveryRisk(
  requestId: string,
  decision: "RELEASE" | "UPHOLD",
  reason: string,
  stepUpToken?: string | null,
): Promise<RecoveryRequest> {
  return mapRecoveryRequest(await apiRequest<unknown>(
    `/api/v1/recovery/requests/${encodeURIComponent(requestId)}/risk-review`,
    { method: "POST", headers: stepUpHeaders(stepUpToken), body: { decision, reason } },
  ));
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

export async function upsertRecoveryPolicy(policy: RecoveryPolicy, stepUpToken?: string | null): Promise<RecoveryPolicy> {
  const body = await apiRequest<RecoveryPolicy>("/api/v1/recovery/policy", {
    method: "PUT",
    headers: stepUpHeaders(stepUpToken),
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

export async function initiateRecoveryRequest(params: { walletId: string; reason: RecoveryReason }, stepUpToken?: string | null): Promise<RecoveryRequest> {
  return mapRecoveryRequest(await apiRequest<unknown>("/api/v1/recovery/requests", {
    method: "POST",
    headers: stepUpHeaders(stepUpToken),
    body: { walletId: params.walletId, reason: params.reason },
  }));
}

export async function cancelRecoveryRequest(requestId: string): Promise<RecoveryRequest> {
  return mapRecoveryRequest(await apiRequest<unknown>(`/api/v1/recovery/requests/${encodeURIComponent(requestId)}/cancel`, {
    method: "POST",
  }));
}

/**
 * The decision is signed here, with the Guardian's own device key. The platform
 * only verifies it; it cannot sign for a Guardian. The proof also covers the
 * policy snapshot hash, so it cannot be moved to a different request or policy.
 */
export async function decideRecoveryRequest(
  request: RecoveryRequest,
  guardian: Guardian,
  decision: "APPROVE" | "REJECT",
  key: GuardianDeviceKey,
  stepUpToken?: string | null,
): Promise<RecoveryRequest> {
  if (!request.sessionId || !request.challenge || !request.policyHash) {
    throw new Error("The recovery session and server challenge are required.");
  }
  if (key.did !== guardian.guardianDid) {
    throw new Error("This browser does not hold your Guardian key. Bind a new key first.");
  }
  const proof = await signGuardianJwt(key, "guardian-recovery+jwt", {
    sub: guardian.guardianId,
    requestId: request.requestId,
    sessionId: request.sessionId,
    walletId: request.walletId,
    decision,
    challenge: request.challenge,
    policyHash: request.policyHash,
  });
  const body = await apiRequest<{ recovery?: unknown }>(
    `/api/v1/recovery/requests/${encodeURIComponent(request.requestId)}/${decision === "APPROVE" ? "approve" : "reject"}`,
    {
      method: "POST",
      headers: stepUpHeaders(stepUpToken),
      body: { guardianId: guardian.guardianId, challenge: request.challenge, proof },
    },
  );
  return mapRecoveryRequest(body?.recovery);
}

export interface RecoveryTimelineEvent {
  eventId: string;
  eventType: string;
  occurredAt: string;
  guardianId: string | null;
  decision: string | null;
}

/** Audit timeline of one request, readable by its owner and assigned guardians. */
export async function fetchRecoveryTimeline(requestId: string): Promise<RecoveryTimelineEvent[]> {
  const body = await apiRequest<{ items?: unknown }>(`/api/v1/recovery/requests/${encodeURIComponent(requestId)}/timeline`);
  assertShape(Array.isArray(body?.items), "recovery timeline");
  return body.items as RecoveryTimelineEvent[];
}

/** Admin oversight case: read-only, never contains the guardian challenge. */
export interface RecoveryOversightCase {
  requestId: string;
  ownerUserId: string;
  walletId: string;
  reason: string;
  state: RecoveryState;
  minimumApprovals: number;
  guardianCount: number;
  approvalCount: number;
  rejectionCount: number;
  policyVersion: number;
  timeLockSeconds: number;
  approvalExpiresAt: string;
  expiresAt: string;
  executableAfter: string | null;
  createdAt: string;
  updatedAt: string;
  attemptCount: number;
  failureCode: string | null;
  successorDid: string | null;
  completedAt: string | null;
  riskLevel: string;
  riskStatus: string;
}

export async function fetchRecoveryOversight(state?: RecoveryState): Promise<RecoveryOversightCase[]> {
  const query = state ? `?state=${encodeURIComponent(state)}` : "";
  const body = await apiRequest<{ items?: unknown }>(`/api/v1/recovery/admin/requests${query}`);
  assertShape(Array.isArray(body?.items), "recovery oversight list");
  return (body.items as RecoveryOversightCase[]).map((item) => ({ ...item, state: normalizeRecoveryState(item.state) }));
}

export async function fetchRecoveryOversightCase(
  requestId: string,
): Promise<{ case: RecoveryOversightCase; timeline: RecoveryTimelineEvent[] }> {
  const body = await apiRequest<{ case?: RecoveryOversightCase; timeline?: unknown }>(
    `/api/v1/recovery/admin/requests/${encodeURIComponent(requestId)}`,
  );
  assertShape(body?.case && Array.isArray(body.timeline), "recovery oversight case");
  return {
    case: { ...body.case, state: normalizeRecoveryState(body.case.state) },
    timeline: body.timeline as RecoveryTimelineEvent[],
  };
}
