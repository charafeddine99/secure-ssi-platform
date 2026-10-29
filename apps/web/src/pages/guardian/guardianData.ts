import { ACTIVE_RECOVERY_STATES, fetchGuardians, fetchRecoveryRequests, type Guardian, type RecoveryRequest } from "../../api/recovery.ts";

export interface GuardianAssignment {
  request: RecoveryRequest;
  guardian: Guardian;
}

/** Requests for wallets where the signed-in user is an ACTIVE guardian (never their own wallet). */
export function assignmentsFor(userId: string, requests: RecoveryRequest[], guardians: Guardian[]): GuardianAssignment[] {
  const result: GuardianAssignment[] = [];
  for (const request of requests) {
    if (request.ownerUserId === userId) continue;
    const guardian = guardians.find((g) => g.walletId === request.walletId && g.guardianUserId === userId && g.status === "ACTIVE");
    if (guardian) result.push({ request, guardian });
  }
  return result;
}

export async function loadAssignments(userId: string): Promise<GuardianAssignment[]> {
  const [requests, guardians] = await Promise.all([fetchRecoveryRequests(50), fetchGuardians()]);
  return assignmentsFor(userId, requests, guardians);
}

export const isOpen = (request: RecoveryRequest): boolean => request.status === "PENDING_APPROVALS";
export const isActive = (request: RecoveryRequest): boolean => ACTIVE_RECOVERY_STATES.includes(request.status);
