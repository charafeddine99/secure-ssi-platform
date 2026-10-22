/**
 * Real Backend API Integration Client for Secure SSI Platform
 * Connects frontend directly to:
 * - API Gateway (Port 8000)
 * - SSI Core & Identity Persistence Service (Port 8001)
 * - AI Fraud & Threat Detection Service (Port 8002)
 */

const viteEnvironment = (import.meta as ImportMeta & {
  env?: { VITE_API_BASE_URL?: string };
}).env;

export const GATEWAY_BASE_URL =
  viteEnvironment?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
export const SSI_CORE_BASE_URL = "http://127.0.0.1:8001";
export const FRAUD_BASE_URL = "http://127.0.0.1:8002";
export const RECOVERY_SERVICE_BASE_URL = "http://127.0.0.1:8003";

export type CredentialStatus = "ACTIVE" | "SUSPENDED" | "REVOKED" | "EXPIRED" | "UNKNOWN";

export interface BackendCredential {
  id: string;
  user_did: string;
  wallet_address: string;
  credential_type: string;
  title: string;
  category: string;
  issuer: string;
  issuer_name: string;
  issued_date: string;
  expiry_date: string;
  status: CredentialStatus;
  claims: Record<string, unknown>;
  proof_value: string;
  ai_risk_score: number | null;
  raw_credential?: Record<string, unknown>;
  zkp_predicate?: string;
  created_at: string;
  status_list_id?: string;
  status_list_index?: number;
}

export interface BackendGuardian {
  id: number;
  guardian_id: string;
  guardian_user_id: string;
  wallet_address: string;
  guardian_name: string;
  guardian_role: string;
  guardian_did: string;
  guardian_address: string;
  approved: number;
  created_at: string;
}

export interface BackendAuditLog {
  id: number;
  event_type: string;
  actor_did: string;
  target_wallet: string;
  risk_score: number;
  details: Record<string, unknown>;
  created_at: string;
}

export interface BlockchainStatus {
  connected: boolean;
  network: string;
  chainId: number;
  currentBlockNumber?: number | null;
  contracts: Record<string, string>;
  status?: string;
  // Accepted only for legacy gateway responses while active consumers migrate.
  block_number?: number;
  chain_id?: number;
  recovery_status?: unknown;
}

export interface GatewayStatus {
  gateway_status: string;
  system_health: string;
  services: {
    identity_service: string;
    fraud_service: string;
    recovery_service: string;
    blockchain_node?: string;
  };
  blockchain?: BlockchainStatus;
  database?: unknown;
}

export interface SmartContractInfo {
  name: string;
  address: string;
  purpose: string;
  methods: string[];
  status: string;
  deploymentVerified?: boolean | null;
}

export interface FraudModelStats {
  model_type: string;
  model_version: string;
  model_status: "NOT_TRAINED" | string;
  evaluation_status: string;
  dataset_label: string;
  advisory_only: boolean;
  risk_signals: string[];
}

export interface OnChainAnchor {
  anchorId: string;
  eventType: string;
  eventHash: string;
  contractType: string;
  contractAddress: string;
  network: string;
  chainId: number;
  status: string;
  createdAt: string;
  subjectId?: string;
  txHash?: string;
  blockNumber?: number;
  confirmedAt?: string;
  errorMessage?: string;
}

interface RawBackendCredential {
  credentialId?: string;
  holderDid?: string;
  status?: string;
  issuanceDate?: string;
  expirationDate?: string;
  statusListId?: string;
  statusListIndex?: number;
  credential?: Record<string, unknown>;
}

function normalizeCredentialStatus(status: unknown): CredentialStatus {
  if (typeof status !== "string") return "UNKNOWN";
  const normalized = status.toUpperCase();
  return ["ACTIVE", "SUSPENDED", "REVOKED", "EXPIRED"].includes(normalized)
    ? normalized as CredentialStatus
    : "UNKNOWN";
}

export interface HolderWallet {
  walletId: string;
  holderDid: string;
}

/** Resolve or create the authenticated user's server-managed prototype wallet. */
export async function getOrCreateHolderWallet(): Promise<HolderWallet> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in before opening a holder wallet.");
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };

  const meResponse = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/auth/me`, { headers });
  if (!meResponse.ok) throw new Error(`Could not resolve the signed-in account (HTTP ${meResponse.status}).`);
  const currentUser = await meResponse.json();
  if (typeof currentUser.id !== "string" || !currentUser.id) {
    throw new Error("Identity Service did not return an account identifier.");
  }

  const storageKey = `ssi_holder_wallet_id:${currentUser.id}`;
  const cachedWalletId = localStorage.getItem(storageKey);
  if (cachedWalletId) {
    const walletResponse = await fetch(
      `${GATEWAY_BASE_URL}/api/v1/identity/wallets/${encodeURIComponent(cachedWalletId)}`,
      { headers }
    );
    if (walletResponse.ok) {
      const wallet = await walletResponse.json();
      return { walletId: wallet.walletId, holderDid: wallet.holderDid };
    }
    if (walletResponse.status !== 404) {
      throw new Error(`Could not read the holder wallet (HTTP ${walletResponse.status}).`);
    }
    localStorage.removeItem(storageKey);
  }

  const createResponse = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/wallets`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
  if (!createResponse.ok) {
    const data = await createResponse.json().catch(() => ({}));
    throw new Error(data.detail || `Could not create the holder wallet (HTTP ${createResponse.status}).`);
  }
  const wallet = await createResponse.json();
  if (typeof wallet.walletId !== "string" || typeof wallet.holderDid !== "string") {
    throw new Error("Identity Service returned an incomplete holder wallet.");
  }
  localStorage.setItem(storageKey, wallet.walletId);
  return { walletId: wallet.walletId, holderDid: wallet.holderDid };
}

/** Fetch only the current authenticated holder's wallet inventory. */
export async function fetchCredentials(
  userDid?: string,
  walletAddress?: string,
  walletId?: string
): Promise<BackendCredential[]> {
  void userDid;
  void walletAddress;
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in before loading wallet credentials.");
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const wallet = walletId ? { walletId } : await getOrCreateHolderWallet();
  const res = await fetch(
    `${GATEWAY_BASE_URL}/api/v1/identity/wallets/${encodeURIComponent(wallet.walletId)}/credentials`,
    { headers }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Could not load wallet credentials (HTTP ${res.status}).`);
  }
  const data = await res.json();
  const credentials = Array.isArray(data.credentials) ? data.credentials as RawBackendCredential[] : [];
  return credentials.flatMap((item) => {
    const raw = item.credential || {};
    const rawSubject = raw.credentialSubject;
    const subject = rawSubject && typeof rawSubject === "object" && !Array.isArray(rawSubject)
      ? { ...(rawSubject as Record<string, unknown>) }
      : {};
    const holderDid = typeof subject.id === "string" ? subject.id : item.holderDid || "";
    delete subject.id;
    const rawTypes = raw.type;
    const types = Array.isArray(rawTypes) ? rawTypes.filter((value): value is string => typeof value === "string") : [];
    const credentialType = types.find((value) => value !== "VerifiableCredential") || "Credential";
    const issuerValue = raw.issuer;
    const issuer = typeof issuerValue === "string"
      ? issuerValue
      : issuerValue && typeof issuerValue === "object" && typeof (issuerValue as { id?: unknown }).id === "string"
        ? (issuerValue as { id: string }).id
        : "";
    const proof = raw.proof && typeof raw.proof === "object" ? raw.proof as Record<string, unknown> : {};
    const credentialId = item.credentialId || (typeof raw.id === "string" ? raw.id : "");
    if (!credentialId) return [];
    return [{
      id: credentialId,
      user_did: holderDid,
      wallet_address: "",
      credential_type: credentialType,
      title: credentialType,
      category: "GENERAL",
      issuer,
      issuer_name: issuer || "Issuer not supplied",
      issued_date: typeof raw.validFrom === "string" ? raw.validFrom : item.issuanceDate || "",
      expiry_date: typeof raw.validUntil === "string" ? raw.validUntil : item.expirationDate || "",
      status: normalizeCredentialStatus(item.status),
      claims: subject,
      proof_value: typeof proof.proofValue === "string" ? proof.proofValue : "",
      ai_risk_score: null,
      created_at: item.issuanceDate || "",
      status_list_id: item.statusListId,
      status_list_index: item.statusListIndex,
      raw_credential: raw
    }];
  });
}

/**
 * Directly sign a local prototype credential via the Identity Service.
 * This endpoint does not create an OID4VCI offer or a blockchain receipt.
 */
export async function issueCredential(payload: {
  wallet_address: string;
  did_id: string;
  credential_type: string;
  title?: string;
  category?: string;
  claims: Record<string, unknown>;
}): Promise<{
  success: boolean;
  credential?: Record<string, unknown>;
  txHash?: string;
  error?: string;
}> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/credentials/sign`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        credential: {
          "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1"
          ],
          id: `urn:uuid:${crypto.randomUUID()}`,
          type: ["VerifiableCredential", payload.credential_type],
          issuer: "did:web:synthetic-issuer.local",
          validFrom: new Date().toISOString(),
          credentialSubject: {
            id: payload.did_id,
            ...payload.claims
          }
        }
      })
    });

    if (res.ok) {
      const data = await res.json();
      return { success: true, credential: data.credential || data };
    }
    const data = await res.json().catch(() => ({}));
    return {
      success: false,
      error: typeof data.detail === "string" ? data.detail : `Credential signing failed (HTTP ${res.status}).`
    };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : "Bağlantı hatası";
    return { success: false, error: errorMsg };
  }
}

/**
 * Revoke credential in real database via Gateway / Identity Service
 */
export async function revokeCredential(credentialId: string, reason: string = "UNSPECIFIED"): Promise<boolean> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/credentials/${encodeURIComponent(credentialId)}/revoke`, {
    method: "POST",
    headers,
    body: JSON.stringify({ reason })
  });
  if (res.ok) return true;
  const data = await res.json().catch(() => ({}));
  throw new Error(data.detail || `Revocation failed (HTTP ${res.status})`);
}

export interface CredentialStatusSnapshot {
  credential_id: string;
  status: CredentialStatus;
  revoked: boolean;
  revocation_reason?: string | null;
  revoked_at?: string | null;
}

export async function fetchCredentialStatus(credentialId: string): Promise<CredentialStatusSnapshot> {
  const response = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/credentials/${encodeURIComponent(credentialId)}/status`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Could not read credential status (HTTP ${response.status}).`);
  if (typeof data.credential_id !== "string" || typeof data.status !== "string") {
    throw new Error("Credential status service returned an invalid response.");
  }
  return data as CredentialStatusSnapshot;
}

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
  createdAt?: string;
  updatedAt?: string;
}

function isRecoveryPolicyForWallet(value: unknown, walletId: string): value is RecoveryPolicy {
  if (typeof value !== "object" || value === null) return false;
  const policy = value as Partial<RecoveryPolicy>;
  const integerAtLeast = (candidate: unknown, minimum: number): candidate is number =>
    typeof candidate === "number" && Number.isInteger(candidate) && candidate >= minimum;

  return policy.walletId === walletId
    && integerAtLeast(policy.minimumApprovals, 1)
    && integerAtLeast(policy.maximumGuardians, policy.minimumApprovals)
    && policy.maximumGuardians <= 32
    && integerAtLeast(policy.approvalWindowSeconds, 60)
    && integerAtLeast(policy.timeLockSeconds, 0)
    && policy.timeLockSeconds <= 30 * 24 * 60 * 60
    && integerAtLeast(policy.recoveryExpirationSeconds, policy.approvalWindowSeconds + policy.timeLockSeconds)
    && integerAtLeast(policy.maximumAttempts, 1)
    && policy.maximumAttempts <= 20
    && integerAtLeast(policy.cooldownSeconds, 0)
    && typeof policy.allowCancellation === "boolean";
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

export interface RecoveryRequest {
  requestId: string;
  sessionId?: string;
  ownerUserId?: string;
  walletId: string;
  guardianCount?: number | null;
  status: RecoveryState;
  challenge?: string;
  reason: string;
  approvalsCount?: number | null;
  requiredCount?: number | null;
  createdAt: string;
  expiresAt: string;
  timelockExpiresAt?: string | null;
  executedAt?: string | null;
  failureCode?: string | null;
  predecessorKeyId?: string | null;
  successorKeyId?: string | null;
  predecessorDid?: string | null;
  successorDid?: string | null;
  txHash?: string | null;
}

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

export interface GuardianAssignment {
  guardianId: string;
  walletId: string;
  guardianUserId: string;
  guardianDid: string;
  displayName: string;
  verificationMethod: string;
  status: "ACTIVE" | "SUSPENDED" | "REVOKED" | "REMOVED";
  createdAt: string;
  updatedAt?: string;
}

interface RawBackendGuardianItem {
  guardianId?: string;
  guardianUserId?: string;
  walletId?: string;
  displayName?: string;
  label?: string;
  guardianName?: string;
  role?: string;
  guardianDid?: string;
  did?: string;
  guardianAddress?: string;
  status?: string;
  createdAt?: string;
}

interface RawRecoveryRequestItem {
  requestId: string;
  walletId: string;
  ownerUserId?: string;
  sessionId?: string;
  state?: string;
  status?: string;
  challenge?: string;
  reason?: string;
  approvalCount?: number;
  approvalsCount?: number;
  minimumApprovals?: number;
  guardianCount?: number;
  requiredCount?: number;
  createdAt?: string;
  expiresAt?: string;
  timelockExpiresAt?: string | null;
  executableAfter?: string | null;
  executedAt?: string | null;
  result?: {
    predecessorKeyId?: string;
    successorKeyId?: string;
    predecessorDid?: string;
    successorDid?: string;
    completedAt?: string;
  } | null;
  failureCode?: string | null;
  predecessorKeyId?: string | null;
  successorKeyId?: string | null;
  predecessorDid?: string | null;
  successorDid?: string | null;
  txHash?: string | null;
}

export function normalizeRecoveryState(value: string | undefined): RecoveryState {
  switch (value) {
    case "PENDING_APPROVALS":
    case "QUORUM_REACHED":
    case "WAITING_TIMELOCK":
    case "READY_FOR_EXECUTION":
    case "EXECUTING":
    case "COMPLETED":
    case "REJECTED":
    case "CANCELLED":
    case "EXPIRED":
    case "FAILED":
    case "RECONCILIATION_REQUIRED":
      return value;
    default:
      return "UNKNOWN";
  }
}

export function mapRecoveryRequest(r: RawRecoveryRequestItem): RecoveryRequest {
  const result = r.result;
  return {
    requestId: r.requestId,
    sessionId: r.sessionId,
    ownerUserId: r.ownerUserId,
    walletId: r.walletId,
    guardianCount: r.guardianCount ?? null,
    status: normalizeRecoveryState(r.state),
    challenge: r.challenge,
    reason: r.reason || "Reason not supplied",
    approvalsCount: r.approvalCount ?? r.approvalsCount ?? null,
    requiredCount: r.minimumApprovals ?? r.requiredCount ?? null,
    createdAt: r.createdAt || "",
    expiresAt: r.expiresAt || "",
    timelockExpiresAt: r.executableAfter ?? r.timelockExpiresAt ?? null,
    executedAt: result?.completedAt ?? r.executedAt ?? null,
    predecessorKeyId: result?.predecessorKeyId,
    successorKeyId: result?.successorKeyId,
    predecessorDid: result?.predecessorDid,
    successorDid: result?.successorDid,
    failureCode: r.failureCode,
    txHash: null,
  };
}

export async function fetchCurrentUserId(): Promise<string> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/auth/me`, { headers });
  const user = await response.json().catch(() => ({}));
  if (!response.ok || typeof user.id !== "string" || !user.id) {
    throw new Error("Could not resolve the signed-in account.");
  }
  return user.id;
}

/**
 * Fetch Guardians list from Recovery Service via Gateway
 */
export async function fetchGuardians(walletId?: string): Promise<BackendGuardian[]> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  const query = walletId ? `?walletId=${encodeURIComponent(walletId)}` : "";

  // 1. Try authoritative Recovery Service via Gateway
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/guardians${query}`, { headers });
    if (res.ok) {
      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
      if (items.length > 0) {
        return items.map((g: RawBackendGuardianItem, idx: number) => ({
          id: idx + 1,
          guardian_id: g.guardianId || "",
          guardian_user_id: g.guardianUserId || "",
          wallet_address: g.walletId || walletId || "",
          guardian_name: g.displayName || g.label || g.guardianName || `Guardian details unavailable (${idx + 1})`,
          guardian_role: g.role || "Role not supplied",
          guardian_did: g.guardianDid || g.did || "",
          guardian_address: g.guardianAddress || "",
          approved: g.status === "ACTIVE" ? 1 : 0,
          created_at: g.createdAt || ""
        }));
      }
    }
  } catch {
    // Fall back to direct recovery service
  }

  // 2. Direct Recovery Service
  try {
    const res = await fetch(`${RECOVERY_SERVICE_BASE_URL}/api/v1/guardians${query}`, { headers });
    if (res.ok) {
      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];
      if (items.length > 0) {
        return items.map((g: RawBackendGuardianItem, idx: number) => ({
          id: idx + 1,
          guardian_id: g.guardianId || "",
          guardian_user_id: g.guardianUserId || "",
          wallet_address: g.walletId || walletId || "",
          guardian_name: g.displayName || `Guardian details unavailable (${idx + 1})`,
          guardian_role: g.role || "Role not supplied",
          guardian_did: g.guardianDid || g.did || "",
          guardian_address: g.guardianAddress || "",
          approved: g.status === "ACTIVE" ? 1 : 0,
          created_at: g.createdAt || ""
        }));
      }
    }
  } catch {
    // Continue
  }

  return [];
}

/**
 * Fetch all recovery petitions/requests
 */
export async function fetchRecoveryRequests(limit: number = 50): Promise<RecoveryRequest[]> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  // 1. Try Gateway
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/requests?limit=${limit}`, { headers });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.items)) {
        return data.items.map((r: RawRecoveryRequestItem) => mapRecoveryRequest(r));
      }
    }
  } catch {
    // Continue
  }

  // 2. Direct Recovery Service
  try {
    const res = await fetch(`${RECOVERY_SERVICE_BASE_URL}/api/v1/recovery/requests?limit=${limit}`, { headers });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.items)) {
        return data.items.map((r: RawRecoveryRequestItem) => mapRecoveryRequest(r));
      }
    }
  } catch {
    // Continue
  }

  return [];
}

/**
 * Fetch a single recovery request by ID
 */
export async function fetchRecoveryRequestById(requestId: string): Promise<RecoveryRequest | null> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/requests/${requestId}`, { headers });
    if (res.ok) {
      const r = await res.json();
      return mapRecoveryRequest(r as RawRecoveryRequestItem);
    }
  } catch {
    // Continue
  }

  const all = await fetchRecoveryRequests(10);
    return all.find((item) => item.requestId === requestId) || null;
}

/**
 * Create a new social recovery request for a wallet
 */
export async function initiateRecoveryRequest(params: {
  walletId: string;
  reason: string;
}): Promise<RecoveryRequest> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const payload = {
    walletId: params.walletId,
    reason: params.reason
  };

  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/requests`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    const r = await res.json();
    return mapRecoveryRequest(r as RawRecoveryRequestItem);
  }

  const data = await res.json().catch(() => ({}));
  throw new Error(data.detail || `Recovery request failed (HTTP ${res.status})`);
}

/**
 * Cancel an active recovery request (e.g. during time-lock)
 */
export async function cancelRecoveryRequest(requestId: string): Promise<RecoveryRequest> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/requests/${requestId}/cancel`, {
    method: "POST",
    headers
  });

  if (res.ok) {
    const r = await res.json();
    return mapRecoveryRequest(r as RawRecoveryRequestItem);
  }

  const data = await res.json().catch(() => ({}));
  throw new Error(data.detail || `Cancel recovery failed (HTTP ${res.status})`);
}

async function createGuardianDecisionProof(
  request: RecoveryRequest,
  guardianId: string,
  guardianDid: string,
  decision: "APPROVE" | "REJECT",
  headers: Record<string, string>,
): Promise<string> {
  if (!request.sessionId || !request.challenge || !request.walletId || !guardianDid) {
    throw new Error("Recovery session, challenge, wallet, and assigned Guardian DID are required.");
  }
  const response = await fetch(
    `${GATEWAY_BASE_URL}/api/v1/identity/wallets/guardian-recovery-proof`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        requestId: request.requestId,
        sessionId: request.sessionId,
        guardianId,
        walletId: request.walletId,
        guardianDid,
        challenge: request.challenge,
        decision,
      }),
    },
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.guardianDid !== guardianDid || typeof data.proof !== "string") {
    throw new Error(data.message || data.detail || "The registered Guardian DID could not sign this recovery decision.");
  }
  return data.proof;
}

/** Sign a request-bound Guardian decision, then submit it for DID verification. */
export async function approveRecoveryPetition(
  request: RecoveryRequest,
  guardianId: string,
  guardianDid: string,
): Promise<{ success: true; recovery: RecoveryRequest }> {
  if (!request.requestId || !guardianId || !request.challenge) {
    throw new Error("Recovery request, Guardian assignment, and server challenge are required.");
  }
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
  const proof = await createGuardianDecisionProof(
    request,
    guardianId,
    guardianDid,
    "APPROVE",
    headers,
  );

  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/requests/${request.requestId}/approve`, {
    method: "POST",
    headers,
    body: JSON.stringify({ guardianId, challenge: request.challenge, proof })
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || data.detail || `Recovery approval failed (HTTP ${res.status})`);
  }
  const data = await res.json();
  return { success: true, recovery: mapRecoveryRequest(data.recovery as RawRecoveryRequestItem) };
}

/**
 * Reject a recovery petition
 */
export async function rejectRecoveryPetition(
  request: RecoveryRequest,
  guardianId: string,
  guardianDid: string,
): Promise<{ success: true; recovery: RecoveryRequest }> {
  if (!request.requestId || !guardianId || !request.challenge) {
    throw new Error("Recovery request, Guardian assignment, and server challenge are required.");
  }
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
  const proof = await createGuardianDecisionProof(
    request,
    guardianId,
    guardianDid,
    "REJECT",
    headers,
  );

  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/requests/${request.requestId}/reject`, {
    method: "POST",
    headers,
    body: JSON.stringify({ guardianId, challenge: request.challenge, proof })
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || data.detail || `Recovery rejection failed (HTTP ${res.status})`);
  }
  const data = await res.json();
  return { success: true, recovery: mapRecoveryRequest(data.recovery as RawRecoveryRequestItem) };
}

/**
 * Fetch Recovery Policy for a wallet (M-of-N threshold, time-lock)
 */
export async function fetchRecoveryPolicy(walletId: string): Promise<RecoveryPolicy | null> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/policy?walletId=${encodeURIComponent(walletId)}`, { headers });
    if (res.ok) {
      const policy: unknown = await res.json();
      return isRecoveryPolicyForWallet(policy, walletId) ? policy : null;
    }
  } catch {
    // Continue
  }

  return null;
}

/**
 * Upsert Recovery Policy for a wallet
 */
export async function upsertRecoveryPolicy(policy: {
  walletId: string;
  minimumApprovals: number;
  maximumGuardians: number;
  approvalWindowSeconds: number;
  timeLockSeconds: number;
  recoveryExpirationSeconds: number;
  maximumAttempts: number;
  cooldownSeconds: number;
  allowCancellation: boolean;
}): Promise<RecoveryPolicy> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/recovery/policy`, {
    method: "PUT",
    headers,
    body: JSON.stringify(policy)
  });

  if (res.ok) {
    return await res.json();
  }

  const errData = await res.json().catch(() => ({}));
  throw new Error(errData.detail || `Update recovery policy failed (HTTP ${res.status})`);
}

/**
 * Legacy alias for approveGuardian
 */
export async function approveGuardian(guardianId: number, walletAddress?: string): Promise<{
  success: boolean;
  onChainTx?: string;
  error?: string;
}> {
  void guardianId;
  void walletAddress;
  return { success: false, error: "Legacy recovery approvals are disabled; use the request-bound Guardian flow." };
}

export const approveGuardianRecovery = async (
  request: RecoveryRequest,
  guardianAddress: string,
  guardianDid: string,
) => {
  return approveRecoveryPetition(request, guardianAddress, guardianDid);
};

/**
 * Fetch audit logs from authoritative persistence layer
 */
export async function fetchAuditLogs(filterType?: string, limit: number = 100): Promise<BackendAuditLog[]> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in with an authorized administrator account to view audit events.");
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };

  const queryParams = new URLSearchParams();
  if (filterType && filterType !== "ALL") queryParams.append("event_type", filterType);
  queryParams.append("limit", String(limit));

  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/audit_logs?${queryParams.toString()}`, { headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : `Could not load audit events (HTTP ${res.status}).`);
  }
  const events = data.audit_logs || data.events;
  if (!Array.isArray(events)) throw new Error("Audit service returned an invalid event list.");
  return events;
}

/**
 * Fetch blockchain status (Hardhat Node)
 */
export async function fetchBlockchainStatus(): Promise<BlockchainStatus | null> {
  // 1. Try Gateway proxy
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/blockchain/status`);
    if (res.ok) return await res.json();
  } catch {
    // Continue
  }

  // 2. Try Identity Service direct
  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/blockchain/status`);
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("fetchBlockchainStatus fallback:", err);
  }
  return null;
}

/**
 * Fetch detailed smart contracts registry from Web3 bridge
 */
export async function fetchBlockchainContracts(): Promise<SmartContractInfo[]> {
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/blockchain/contracts`);
    if (res.ok) {
      const data = await res.json();
      return data.contracts || [];
    }
  } catch {
    // Fallback to direct identity endpoint
  }

  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/blockchain/contracts`);
    if (res.ok) {
      const data = await res.json();
      return data.contracts || [];
    }
  } catch (err) {
    console.warn("fetchBlockchainContracts fallback:", err);
  }

  return [];
}

/**
 * Fetch recent on-chain anchor transactions
 */
export async function fetchBlockchainAnchors(limit: number = 20): Promise<OnChainAnchor[]> {
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/blockchain/anchors?limit=${limit}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("fetchBlockchainAnchors fallback:", err);
  }
  return [];
}

/**
 * Fetch gateway status from Port 8000
 */
export async function fetchGatewayStatus(): Promise<GatewayStatus | null> {
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/system/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("fetchGatewayStatus fallback:", err);
    return null;
  }
}

/**
 * Fetch AI Fraud Model Stats from Fraud Service
 */
export async function fetchFraudStats(): Promise<FraudModelStats | null> {
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/fraud/stats`);
    if (res.ok) return await res.json();
  } catch {
    // Continue
  }

  try {
    const res = await fetch(`${FRAUD_BASE_URL}/api/v1/fraud/stats`);
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("fetchFraudStats fallback:", err);
  }
  return null;
}

/**
 * Fetch database persistence stats from Identity Service
 */
export async function fetchDatabaseStats(): Promise<Record<string, unknown> | null> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in with an authorized administrator account to view persistence statistics.");
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/database/stats`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Could not load persistence statistics (HTTP ${res.status}).`);
  return data;
}

/**
 * Release an account from quarantine
 */
export async function releaseAccountQuarantine(did: string): Promise<boolean> {
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/fraud/quarantine/${encodeURIComponent(did)}`, {
      method: "DELETE"
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Evaluate a risk heuristic; service failure is surfaced without a fallback score. */
export async function evaluateAiRisk(context: {
  did_id: string;
  timestamp: number;
  ip_address: string;
  device_fingerprint: string;
  recent_failed_attempts: number;
}): Promise<{
  risk_score: number;
  verdict: string;
  is_anomalous: boolean;
}> {
  try {
    const res = await fetch(`${FRAUD_BASE_URL}/api/fraud_detection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        did_id: context.did_id,
        timestamp: context.timestamp,
        ip_address: context.ip_address,
        device_fingerprint: context.device_fingerprint,
        recent_failed_attempts: context.recent_failed_attempts
      })
    });
    if (!res.ok) throw new Error(`Fraud service returned HTTP ${res.status}`);
    const data = await res.json();
    return {
      risk_score: data.risk_score / 100,
      verdict: data.risk_score > 70 ? "HIGH_RISK" : "LOW_RISK",
      is_anomalous: data.risk_score > 70
    };
  } catch (err) {
    console.warn("Risk heuristic unavailable:", err);
    throw err;
  }
}

export interface FraudAssessmentResult {
  risk_score: number;
  is_fraudulent: boolean;
  anomaly_score?: number;
  reasons: string[];
  model_version: string;
  advisory_only: boolean;
  risk_signals?: string[];
}

/**
 * Assess fraud risk through Gateway / Fraud Service
 */
export async function assessFraudRisk(payload: {
  wallet_address: string;
  did_id: string;
  ip_address: string;
  device_fingerprint: string;
  recent_failed_attempts: number;
}): Promise<FraudAssessmentResult> {
  try {
    const res = await fetch(`${FRAUD_BASE_URL}/api/fraud_detection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wallet_address: payload.wallet_address,
        did_id: payload.did_id,
        ip_address: payload.ip_address,
        device_fingerprint: payload.device_fingerprint,
        recent_failed_attempts: payload.recent_failed_attempts
      })
    });
    if (!res.ok) throw new Error(`Fraud service returned HTTP ${res.status}`);
    const data = await res.json();
    if (typeof data.risk_score !== "number" || typeof data.is_fraudulent !== "boolean") {
      throw new Error("Fraud service returned an invalid assessment.");
    }
    return {
      risk_score: data.risk_score,
      is_fraudulent: data.is_fraudulent,
      anomaly_score: data.anomaly_score,
      reasons: Array.isArray(data.reasons) ? data.reasons : [],
      model_version: data.model_version,
      advisory_only: data.advisory_only === true,
      risk_signals: Array.isArray(data.risk_signals) ? data.risk_signals : undefined
    };
  } catch (err) {
    console.warn("assessFraudRisk unavailable:", err);
    throw err;
  }
}

/**
 * Presentation verification result model
 */
export interface PresentationVerificationResult {
  verified: boolean;
  status: "VERIFIED" | "REJECTED" | "UNAVAILABLE" | "ERROR";
  signature_valid?: boolean;
  challenge_valid?: boolean;
  claims?: Record<string, unknown>;
  details?: unknown;
  errors: string[];
}

interface VerificationResponseData {
  valid?: boolean;
  status?: string;
  result?: {
    finalPolicyResult?: string;
    signatureValid?: boolean;
    challengeValid?: boolean;
  };
  signature_valid?: boolean;
  challenge_valid?: boolean;
  claims?: Record<string, unknown>;
  disclosedClaims?: Record<string, unknown>;
  errors?: string[];
  rejection_codes?: string[];
  detail?: string | Record<string, unknown>;
}

export async function verifyPresentation(payload: Record<string, unknown>): Promise<PresentationVerificationResult> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const endpoints = [
    `${GATEWAY_BASE_URL}/api/v1/identity/presentations/verify`,
    `${SSI_CORE_BASE_URL}/api/v1/presentations/verify`
  ];

  let lastNetworkError: Error | null = null;
  let lastHttpError: { status: number; statusText: string; body?: unknown } | null = null;

  for (const url of endpoints) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(payload)
      });

      let data: VerificationResponseData | null = null;
      try {
        data = await res.json();
      } catch {
        // non-JSON response body
      }

      if (res.ok && data) {
        const hasPolicyResult = Object.prototype.hasOwnProperty.call(data, "result");
        const isValid = typeof data.result?.finalPolicyResult === "string"
          ? data.result.finalPolicyResult === "ACCEPTED"
          : hasPolicyResult
          ? false
          : data.valid === true || data.status === "VERIFIED";

        const status: "VERIFIED" | "REJECTED" = isValid ? "VERIFIED" : "REJECTED";
        const errors: string[] = Array.isArray(data.errors)
          ? data.errors
          : Array.isArray(data.rejection_codes)
          ? data.rejection_codes
          : (!isValid ? ["Cryptographic or policy verification failed."] : []);

        return {
          verified: isValid,
          status,
          signature_valid: data.result?.signatureValid ?? data.signature_valid,
          challenge_valid: data.result?.challengeValid ?? data.challenge_valid,
          claims: data.claims || data.disclosedClaims || (payload.disclosed_claims as Record<string, unknown>) || {},
          details: data,
          errors
        };
      }

      if (!res.ok) {
        const errors: string[] = [];
        if (data && data.detail) {
          errors.push(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
        } else if (data && Array.isArray(data.errors)) {
          errors.push(...data.errors);
        } else {
          errors.push(`Verification service responded with HTTP ${res.status}: ${res.statusText}`);
        }

        if (res.status >= 400 && res.status < 500) {
          return {
            verified: false,
            status: "REJECTED",
            claims: (payload.disclosed_claims as Record<string, unknown>) || {},
            details: data || { status: res.status, statusText: res.statusText },
            errors
          };
        }

        lastHttpError = { status: res.status, statusText: res.statusText, body: data };
      }
    } catch (err: unknown) {
      lastNetworkError = err instanceof Error ? err : new Error(String(err));
    }
  }

  // Network transport failure or internal server error: fail closed with explicit UNAVAILABLE / ERROR
  if (lastHttpError) {
    const emptyClaims: Record<string, unknown> = {};
    return {
      verified: false,
      status: "ERROR",
      claims: (payload.disclosed_claims as Record<string, unknown>) || emptyClaims,
      details: lastHttpError,
      errors: [
        `Verification service error (HTTP ${lastHttpError.status}): ${lastHttpError.statusText || "Internal Server Error"}`
      ]
    };
  }

  const emptyClaims: Record<string, unknown> = {};
  return {
    verified: false,
    status: "UNAVAILABLE",
    claims: (payload.disclosed_claims as Record<string, unknown>) || emptyClaims,
    details: { error: lastNetworkError?.message || "Connection refused" },
    errors: [
      `Verification service unreachable: ${lastNetworkError?.message || "Network/Transport connection failed"}`
    ]
  };
}

/**
 * Approve recovery guardian alias
 */
export async function approveGuardianRecoveryLegacy(
  guardianId: number,
  walletAddress: string
): Promise<{ success: boolean; tx_hash?: string }> {
  const res = await approveGuardian(guardianId, walletAddress);
  return {
    success: res.success,
    tx_hash: res.onChainTx || undefined
  };
}

/**
 * Quarantine wallet on-chain
 */
export async function quarantineWallet(
  walletAddress: string,
  reason: string
): Promise<{ success: boolean; tx_hash?: string }> {
  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/quarantine_wallet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wallet_address: walletAddress, reason })
    });
    if (!res.ok) return { success: false };
    const data = await res.json();
    const anchor = data.blockchain_anchor || data.anchor || data;
    const confirmed = anchor.status === "CONFIRMED" && typeof anchor.tx_hash === "string";
    return { success: confirmed, tx_hash: confirmed ? anchor.tx_hash : undefined };
  } catch (err) {
    console.warn("quarantineWallet unavailable:", err);
    return { success: false };
  }
}

// ==========================================
// OID4VCI (Issuance) & OID4VP (Presentation)
// ==========================================

export interface Oid4vciOffer {
  offerId: string;
  credentialIssuer: string;
  credentialConfigurationIds: string[];
  preAuthorizedCode: string;
  status: string;
  deepLinkUri: string;
  qrPayload: string;
  expiresAt: string;
  subjectData: Record<string, unknown>;
}

export interface Oid4vciCredentialConfiguration {
  format?: string;
  scope?: string;
  cryptographic_binding_methods_supported?: string[];
  credential_signing_alg_values_supported?: string[];
  proof_types_supported?: Record<string, { proof_signing_alg_values_supported?: string[] }>;
  display?: Array<{ name?: string; locale?: string }>;
}

export interface Oid4vciIssuerMetadata {
  credential_issuer: string;
  credential_configurations_supported: Record<string, Oid4vciCredentialConfiguration>;
}

export interface PublicTrustRecord {
  id: string;
  issuerDid: string;
  organizationName: string;
  trustStatus: string;
  trustSource?: string;
  auditMetadata?: Record<string, unknown>;
  roles: string[];
  permittedCredentialTypes: string[];
  validFrom: string;
  validUntil?: string | null;
}

const publicDirectoryRequestSignal = (signal?: AbortSignal): AbortSignal => {
  const timeout = AbortSignal.timeout(10_000);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
};

export async function fetchOid4vciIssuerMetadata(signal?: AbortSignal): Promise<Oid4vciIssuerMetadata> {
  const response = await fetch(
    `${GATEWAY_BASE_URL}/api/v1/oid4vci/.well-known/openid-credential-issuer`,
    { signal: publicDirectoryRequestSignal(signal) },
  );
  if (!response.ok) throw new Error(`Issuer metadata is unavailable (HTTP ${response.status}).`);
  const value = await response.json() as Partial<Oid4vciIssuerMetadata>;
  if (!value.credential_issuer || !value.credential_configurations_supported || typeof value.credential_configurations_supported !== "object") {
    throw new Error("Issuer metadata did not include supported credential configurations.");
  }
  return value as Oid4vciIssuerMetadata;
}

export async function fetchPublicTrustedIssuers(signal?: AbortSignal): Promise<PublicTrustRecord[]> {
  const response = await fetch(
    `${GATEWAY_BASE_URL}/api/v1/identity/trust-registry/issuers?limit=100`,
    { signal: publicDirectoryRequestSignal(signal) },
  );
  if (!response.ok) throw new Error(`Trust Registry is unavailable (HTTP ${response.status}).`);
  const value: unknown = await response.json();
  if (!Array.isArray(value)) throw new Error("Trust Registry returned an invalid issuer list.");
  return value.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Trust Registry returned an invalid issuer record at index ${index}.`);
    }
    const record = item as Record<string, unknown>;
    const read = (camelCase: string, snakeCase = camelCase): unknown => record[camelCase] ?? record[snakeCase];
    const requiredString = (camelCase: string, snakeCase = camelCase): string => {
      const field = read(camelCase, snakeCase);
      if (typeof field !== "string" || !field.trim()) {
        throw new Error(`Trust Registry issuer record at index ${index} is missing ${camelCase}.`);
      }
      return field;
    };
    const stringList = (camelCase: string, snakeCase = camelCase): string[] => {
      const field = read(camelCase, snakeCase);
      if (!Array.isArray(field) || !field.every((entry) => typeof entry === "string")) {
        throw new Error(`Trust Registry issuer record at index ${index} has an invalid ${camelCase} list.`);
      }
      return field;
    };
    const validUntil = read("validUntil", "valid_until");
    if (validUntil !== undefined && validUntil !== null && typeof validUntil !== "string") {
      throw new Error(`Trust Registry issuer record at index ${index} has an invalid validUntil value.`);
    }
    const trustSource = read("trustSource", "trust_source");
    const auditMetadata = read("auditMetadata", "audit_metadata");
    if (trustSource !== undefined && typeof trustSource !== "string") {
      throw new Error(`Trust Registry issuer record at index ${index} has an invalid trustSource value.`);
    }
    if (auditMetadata !== undefined && (!auditMetadata || typeof auditMetadata !== "object" || Array.isArray(auditMetadata))) {
      throw new Error(`Trust Registry issuer record at index ${index} has invalid auditMetadata.`);
    }
    return {
      id: requiredString("id"),
      issuerDid: requiredString("issuerDid", "issuer_did"),
      organizationName: requiredString("organizationName", "organization_name"),
      trustStatus: requiredString("trustStatus", "trust_status"),
      trustSource: trustSource as string | undefined,
      auditMetadata: auditMetadata as Record<string, unknown> | undefined,
      roles: stringList("roles"),
      permittedCredentialTypes: stringList("permittedCredentialTypes", "permitted_credential_types"),
      validFrom: requiredString("validFrom", "valid_from"),
      validUntil: validUntil as string | null | undefined,
    };
  });
}

export interface AdminUserRecord {
  id: string;
  username: string;
  displayName: string;
  roles: string[];
  enabled: boolean;
  issuerDid: string | null;
  issuerOrganizationName: string | null;
  version: number;
}

export interface AdminIssuerScopeOption {
  issuerDid: string;
  organizationName: string;
}

async function adminIdentityRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  const response = await fetch(`${GATEWAY_BASE_URL}/api/v1/identity/admin/users${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!response.ok) {
    let detail = `Identity Service request failed (HTTP ${response.status}).`;
    try {
      const body = await response.json() as { detail?: unknown; message?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (typeof body.message === "string") detail = body.message;
    } catch {
      // Keep the HTTP status as the visible error when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function fetchAdminUsers(): Promise<AdminUserRecord[]> {
  return adminIdentityRequest<AdminUserRecord[]>("");
}

export function fetchAdminIssuerScopeOptions(): Promise<AdminIssuerScopeOption[]> {
  return adminIdentityRequest<AdminIssuerScopeOption[]>("/issuer-options");
}

export function updateAdminIssuerScope(
  userId: string,
  issuerDid: string | null,
  expectedVersion: number,
): Promise<AdminUserRecord> {
  return adminIdentityRequest<AdminUserRecord>(`/${encodeURIComponent(userId)}/issuer-scope`, {
    method: "PUT",
    body: JSON.stringify({ issuerDid, expectedVersion }),
  });
}

export interface NinePointVerificationResult {
  credentialValid: boolean;
  issuerTrusted: boolean;
  signatureValid: boolean;
  holderBindingValid: boolean;
  expirationValid: boolean;
  revocationStatusClear: boolean;
  challengeValid: boolean;
  aiRiskLevel: "LOW" | "MEDIUM" | "HIGH";
  blockchainAnchored: boolean;
  finalPolicyResult: "ACCEPTED" | "REJECTED";
  evaluations: Record<string, string>;
}

export interface Oid4vpSession {
  sessionId: string;
  purpose: string;
  requestedCredentialTypes: string[];
  requestedFields: string[];
  dcqlQuery?: Record<string, unknown>;
  nonce: string;
  status: "PENDING" | "VERIFIED" | "REJECTED" | "EXPIRED";
  consentStatus?: "PENDING" | "GRANTED" | "REJECTED";
  rejectionReason?: string;
  verifierDid?: string;
  clientId?: string;
  deepLinkUri: string;
  qrPayload: string;
  expiresAt: string;
  verificationResult?: NinePointVerificationResult;
  disclosedClaims?: Record<string, unknown>;
  aiRiskScore?: number;
}

export type Oid4vpHolderRequest = Pick<
  Oid4vpSession,
  "sessionId" | "purpose" | "nonce" | "status" | "consentStatus" | "verifierDid" | "clientId" | "deepLinkUri" | "qrPayload" | "expiresAt" | "dcqlQuery"
> & { requestedFields: string[] };

/**
 * Issuer creates standard OID4VCI Credential Offer with QR code
 */
export async function createOid4vciOffer(payload: {
  credentialConfigurationIds: string[];
  subjectData: Record<string, unknown>;
  ttlSeconds?: number;
  userPin?: string;
  token?: string;
}): Promise<Oid4vciOffer> {
  const token = payload.token || localStorage.getItem("ssi_access_token") || "";
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/offers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify({
      credentialConfigurationIds: payload.credentialConfigurationIds,
      subjectData: payload.subjectData,
      ttlSeconds: payload.ttlSeconds || 1800,
      userPin: payload.userPin
    })
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const message = typeof data.detail === "string"
      ? data.detail
      : typeof data.error?.message === "string"
        ? data.error.message
        : `Failed to create OID4VCI offer (HTTP ${res.status}).`;
    throw new Error(message);
  }
  return res.json();
}

/**
 * Holder inspects OID4VCI offer details by offerId
 */
export async function getOid4vciOffer(offerId: string): Promise<Oid4vciOffer> {
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/offers/${offerId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch OID4VCI offer: ${res.status}`);
  }
  return res.json();
}

/**
 * Holder queries pending credential offers authorized for their DID / identity
 */
export async function fetchPendingOffers(token?: string): Promise<Oid4vciOffer[]> {
  const authToken = token || localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!authToken) throw new Error("Sign in before loading credential offers.");
  const headers: Record<string, string> = {
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {})
  };
  let gatewayFailure = "The API Gateway could not load credential offers.";
  try {
    const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/offers`, { headers });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      const offers = Array.isArray(data) ? data : data.offers;
      if (!Array.isArray(offers)) throw new Error("Credential offer service returned an invalid response.");
      return offers;
    }
    gatewayFailure = typeof data.detail === "string" ? data.detail : `Credential offers unavailable (HTTP ${res.status}).`;
    if ([401, 403].includes(res.status)) throw new Error(gatewayFailure);
    if (![404, 502, 503].includes(res.status)) throw new Error(gatewayFailure);
  } catch (cause) {
    if (cause instanceof Error && !cause.message.includes("fetch")) throw cause;
    gatewayFailure = cause instanceof Error ? cause.message : gatewayFailure;
  }

  try {
    const res = await fetch(`${SSI_CORE_BASE_URL}/api/v1/oid4vci/offers`, { headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `Credential offers unavailable (HTTP ${res.status}).`;
      throw new Error(detail);
    }
    const offers = Array.isArray(data) ? data : data.offers;
    if (!Array.isArray(offers)) throw new Error("Credential offer service returned an invalid response.");
    return offers;
  } catch (cause) {
    throw cause instanceof Error ? cause : new Error(gatewayFailure);
  }
}

/** Read offers owned by the authenticated issuer; this is not a credential-issuance count. */
export async function fetchIssuerOffers(): Promise<Oid4vciOffer[]> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in as an issuer to view your offers.");
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/offers?as_issuer=true`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(`Could not load issuer offers (HTTP ${res.status}).`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

/**
 * Holder claims offer using preAuthorizedCode and receives signed W3C VC
 */
export async function claimOid4vciOffer(payload: {
  preAuthorizedCode: string;
  holderDid: string;
  walletId?: string;
  credentialConfigurationId: string;
  userPin?: string;
  token?: string;
}): Promise<{ credential: Record<string, unknown>; credentialId: string; status: string }> {
  const holderToken = payload.token || localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!holderToken) throw new Error("Sign in before claiming a credential offer.");
  if (!payload.walletId) throw new Error("A server-managed holder wallet is required.");

  const tokenResponse = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:pre-authorized_code",
      "pre-authorized_code": payload.preAuthorizedCode,
      ...(payload.userPin ? { user_pin: payload.userPin } : {})
    })
  });
  const tokenData = await tokenResponse.json().catch(() => ({}));
  if (!tokenResponse.ok || typeof tokenData.access_token !== "string" || typeof tokenData.c_nonce !== "string") {
    throw new Error(tokenData.error_description || `OID4VCI token exchange failed (HTTP ${tokenResponse.status}).`);
  }

  const metadataResponse = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/.well-known/openid-credential-issuer`);
  const metadata = await metadataResponse.json().catch(() => ({}));
  if (!metadataResponse.ok || typeof metadata.credential_issuer !== "string") {
    throw new Error(`Could not resolve the configured credential issuer (HTTP ${metadataResponse.status}).`);
  }

  const proofResponse = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/holder-proof`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${holderToken}` },
    body: JSON.stringify({ walletId: payload.walletId, audience: metadata.credential_issuer, nonce: tokenData.c_nonce })
  });
  const proofData = await proofResponse.json().catch(() => ({}));
  if (!proofResponse.ok || typeof proofData.jwt !== "string") {
    throw new Error(proofData.detail || `Could not sign the holder proof (HTTP ${proofResponse.status}).`);
  }
  if (proofData.holderDid !== payload.holderDid) {
    throw new Error("The selected holder DID does not match the authenticated wallet.");
  }

  const credentialResponse = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vci/credential`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenData.access_token}` },
    body: JSON.stringify({
      credentialConfigurationId: payload.credentialConfigurationId,
      proof: { proofType: "jwt", jwt: proofData.jwt },
      walletId: payload.walletId
    })
  });
  const credentialData = await credentialResponse.json().catch(() => ({}));
  if (!credentialResponse.ok || !credentialData.credential || typeof credentialData.credential !== "object") {
    throw new Error(credentialData.error_description || credentialData.detail || `OID4VCI credential request failed (HTTP ${credentialResponse.status}).`);
  }
  const credential = credentialData.credential as Record<string, unknown>;
  const credentialId = typeof credentialData.credentialId === "string"
    ? credentialData.credentialId
    : typeof credential.id === "string" ? credential.id : "";
  if (!credentialId) throw new Error("Identity Service did not return the issued credential identifier.");
  return { credential, credentialId, status: typeof credentialData.status === "string" ? credentialData.status : "UNKNOWN" };
}

/**
 * Verifier initiates standard OID4VP Verification Session with QR code
 */
export async function createOid4vpSession(payload: {
  purpose: string;
  requestedCredentialTypes: string[];
  requestedFields: string[];
  ttlSeconds?: number;
  token?: string;
}): Promise<Oid4vpSession> {
  const token = payload.token || localStorage.getItem("ssi_access_token") || "";
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/requests`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify({
      purpose: payload.purpose,
      requestedCredentialTypes: payload.requestedCredentialTypes,
      requestedFields: payload.requestedFields,
      ttlSeconds: payload.ttlSeconds || 600
    })
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to create OID4VP session: ${res.status} ${err}`);
  }
  return res.json();
}

/**
 * Verifier polls OID4VP session to check live presentation verification status
 */
export async function getOid4vpSession(sessionId: string): Promise<Oid4vpSession> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in as the verifier who created this request before polling its result.");
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/requests/${encodeURIComponent(sessionId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch OID4VP session: ${res.status}`);
  }
  return res.json();
}

/** Load only the protocol request needed by a signed-in Holder consent flow. */
export async function getOid4vpHolderRequest(sessionId: string): Promise<Oid4vpHolderRequest> {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in as the holder to inspect this presentation request.");
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/requests/${encodeURIComponent(sessionId)}/holder-request`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Could not load the Holder presentation request (HTTP ${res.status}).`);
  }
  return res.json();
}

export interface Oid4vpDcqlMatch {
  queryId: string;
  credentialId: string;
  matchedClaims: Record<string, unknown>;
}

export interface Oid4vpDcqlEvaluation {
  isSatisfied: boolean;
  matchedCredentials: Oid4vpDcqlMatch[];
  unsatisfiedReason?: string | null;
  details?: { selectedQueryIds?: string[]; [key: string]: unknown };
}

/** Evaluate only credential documents already loaded from the authenticated wallet. */
export async function evaluateOid4vpSession(
  sessionId: string,
  candidateCredentials: Record<string, unknown>[],
): Promise<Oid4vpDcqlEvaluation> {
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/requests/${encodeURIComponent(sessionId)}/evaluate-dcql`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${requireHolderToken()}`,
    },
    body: JSON.stringify({ candidateCredentials }),
  });
  if (!res.ok) {
    throw new Error(`Could not evaluate the wallet against this request (HTTP ${res.status}).`);
  }
  return res.json();
}

function requireHolderToken(): string {
  const token = localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token") || "";
  if (!token) throw new Error("Sign in as the holder before approving a presentation request.");
  return token;
}

export async function recordWalletOid4vpConsent(payload: {
  sessionId: string;
  walletId: string;
  holderDid: string;
  action: "APPROVE" | "REJECT";
  approvedCredentials?: string[];
  approvedClaims?: Record<string, unknown>;
  rejectedClaims?: string[];
  rejectionReason?: string;
}): Promise<Oid4vpConsentResponse> {
  const token = requireHolderToken();
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/requests/${encodeURIComponent(payload.sessionId)}/wallet-consent`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      walletId: payload.walletId,
      holderDid: payload.holderDid,
      action: payload.action,
      approvedCredentials: payload.approvedCredentials || [],
      approvedClaims: payload.approvedClaims || {},
      rejectedClaims: payload.rejectedClaims || [],
      rejectionReason: payload.rejectionReason,
    }),
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Could not record wallet-bound consent (HTTP ${res.status}): ${error}`);
  }
  return res.json();
}

export async function createWalletOid4vpPresentation(payload: {
  sessionId: string;
  walletId: string;
  credentialIds: string[];
  disclosedClaims: Record<string, unknown>;
}): Promise<{ sessionId: string; vpToken: Record<string, unknown> }> {
  const token = requireHolderToken();
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/wallet-presentation`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      sessionId: payload.sessionId,
      walletId: payload.walletId,
      credentialIds: payload.credentialIds,
      disclosedClaims: payload.disclosedClaims,
    }),
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Could not create a wallet-bound presentation (HTTP ${res.status}): ${error}`);
  }
  return res.json();
}

/**
 * Holder wallet submits the complete signed Verifiable Credential via Direct Post for this profile.
 * The current eddsa-jcs-2022 profile does not provide claim-level cryptographic selective disclosure.
 */
export async function submitOid4vpDirectPost(payload: {
  sessionId: string;
  vpToken: Record<string, unknown>;
  disclosedClaims: Record<string, unknown>;
}): Promise<{ status: string; result: NinePointVerificationResult }> {
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/response`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Direct post failed: ${res.status} ${err}`);
  }
  return res.json();
}

/** @deprecated The anonymous legacy endpoint is disabled; use recordWalletOid4vpConsent. */
export async function rejectOid4vpSession(payload: {
  sessionId: string;
  reason?: string;
  holderDid?: string;
}): Promise<{ sessionId: string; status: string; reason: string }> {
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/requests/${encodeURIComponent(payload.sessionId)}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      reason: payload.reason || "Consent rejected by user",
      holderDid: payload.holderDid,
    })
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to reject OID4VP session: ${res.status} ${err}`);
  }
  return res.json();
}

/** @deprecated The anonymous legacy endpoint is disabled; use recordWalletOid4vpConsent. */
export interface Oid4vpConsentPayload {
  sessionId: string;
  action?: "APPROVE" | "REJECT";
  decision?: "APPROVE" | "REJECT";
  holderDid: string;
  approvedCredentials?: string[];
  approvedClaims?: Record<string, unknown>;
  rejectedClaims?: string[];
  verifierDid?: string;
  clientId?: string;
  nonce?: string;
  purpose?: string;
}

export interface Oid4vpConsentResponse {
  sessionId: string;
  status: string;
  consentStatus: string;
  decisionId?: string;
  action: string;
  decision: string;
  holderDid: string;
  approvedCredentials: string[];
  approvedClaims: Record<string, unknown>;
  rejectedClaims: string[];
  timestamp: string;
  rejectionReason?: string;
}

/** @deprecated The anonymous legacy endpoint is disabled; use recordWalletOid4vpConsent. */
export async function recordOid4vpConsent(payload: Oid4vpConsentPayload): Promise<Oid4vpConsentResponse> {
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/requests/${encodeURIComponent(payload.sessionId)}/consent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision: payload.decision || payload.action || "APPROVE",
      action: payload.action || payload.decision || "APPROVE",
      holderDid: payload.holderDid,
      approvedCredentials: payload.approvedCredentials || [],
      approvedClaims: payload.approvedClaims || {},
      rejectedClaims: payload.rejectedClaims || [],
      verifierDid: payload.verifierDid,
      clientId: payload.clientId,
      nonce: payload.nonce,
      purpose: payload.purpose,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to record consent: ${res.status} ${err}`);
  }
  return res.json();
}

/** @deprecated The legacy server signer is disabled; use createWalletOid4vpPresentation. */
export async function createOid4vpPresentation(payload: {
  sessionId: string;
  disclosedClaims?: Record<string, unknown>;
  holderDid?: string;
  verifiableCredentials?: Record<string, unknown>[];
}): Promise<{ sessionId: string; vpToken: Record<string, unknown> }> {
  const res = await fetch(`${GATEWAY_BASE_URL}/api/v1/oid4vp/presentation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sessionId: payload.sessionId,
      disclosedClaims: payload.disclosedClaims,
      holderDid: payload.holderDid,
      verifiableCredentials: payload.verifiableCredentials || [],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to create signed presentation: ${res.status} ${err}`);
  }
  return res.json();
}


