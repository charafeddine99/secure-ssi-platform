import { ApiError, apiRequest, assertShape, isApiError } from "../lib/http.ts";

export type PolicyResult = "ACCEPTED" | "REJECTED";

export interface VerificationResult {
  credentialValid: boolean;
  issuerTrusted: boolean;
  signatureValid: boolean;
  holderBindingValid: boolean;
  expirationValid: boolean;
  revocationStatusClear: boolean;
  challengeValid: boolean;
  aiRiskLevel: string;
  aiRiskScore?: number;
  blockchainAnchored: boolean;
  finalPolicyResult: PolicyResult;
  details: Record<string, unknown>;
}

export interface Oid4vpSession {
  sessionId: string;
  purpose: string;
  requestedFields: string[];
  dcqlQuery: Record<string, unknown>;
  nonce: string;
  status: string;
  consentStatus: string;
  rejectionReason?: string | null;
  verifierDid: string;
  clientId: string;
  responseUri?: string;
  deepLinkUri: string;
  qrPayload: string;
  expiresAt: string;
  verificationResult: VerificationResult | null;
  disclosedClaims: Record<string, unknown> | null;
}

export type Oid4vpHolderRequest = Omit<Oid4vpSession, "verificationResult" | "disclosedClaims" | "rejectionReason">;

function bool(value: unknown): boolean {
  return value === true;
}

export function parseVerificationResult(value: unknown): VerificationResult | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  // Anything other than an explicit ACCEPTED is treated as a rejection.
  const finalPolicyResult: PolicyResult = raw.finalPolicyResult === "ACCEPTED" ? "ACCEPTED" : "REJECTED";
  return {
    credentialValid: bool(raw.credentialValid),
    issuerTrusted: bool(raw.issuerTrusted),
    signatureValid: bool(raw.signatureValid),
    holderBindingValid: bool(raw.holderBindingValid),
    expirationValid: bool(raw.expirationValid),
    revocationStatusClear: bool(raw.revocationStatusClear),
    challengeValid: bool(raw.challengeValid),
    aiRiskLevel: typeof raw.aiRiskLevel === "string" ? raw.aiRiskLevel : "UNKNOWN",
    aiRiskScore: typeof raw.aiRiskScore === "number" ? raw.aiRiskScore : undefined,
    blockchainAnchored: bool(raw.blockchainAnchored),
    finalPolicyResult,
    details: raw.details && typeof raw.details === "object" ? raw.details as Record<string, unknown> : {},
  };
}

function parseSession(value: unknown): Oid4vpSession {
  const raw = (value ?? {}) as Record<string, unknown>;
  assertShape(typeof raw.sessionId === "string" && typeof raw.nonce === "string", "verification session");
  return {
    sessionId: raw.sessionId as string,
    purpose: typeof raw.purpose === "string" ? raw.purpose : "",
    requestedFields: Array.isArray(raw.requestedFields) ? raw.requestedFields.filter((f): f is string => typeof f === "string") : [],
    dcqlQuery: raw.dcqlQuery && typeof raw.dcqlQuery === "object" ? raw.dcqlQuery as Record<string, unknown> : {},
    nonce: raw.nonce as string,
    status: typeof raw.status === "string" ? raw.status : "UNKNOWN",
    consentStatus: typeof raw.consentStatus === "string" ? raw.consentStatus : "UNKNOWN",
    rejectionReason: typeof raw.rejectionReason === "string" ? raw.rejectionReason : null,
    verifierDid: typeof raw.verifierDid === "string" ? raw.verifierDid : "",
    clientId: typeof raw.clientId === "string" ? raw.clientId : "",
    responseUri: typeof raw.responseUri === "string" ? raw.responseUri : undefined,
    deepLinkUri: typeof raw.deepLinkUri === "string" ? raw.deepLinkUri : "",
    qrPayload: typeof raw.qrPayload === "string" ? raw.qrPayload : "",
    expiresAt: typeof raw.expiresAt === "string" ? raw.expiresAt : "",
    verificationResult: parseVerificationResult(raw.verificationResult),
    disclosedClaims: raw.disclosedClaims && typeof raw.disclosedClaims === "object" ? raw.disclosedClaims as Record<string, unknown> : null,
  };
}

export async function createOid4vpSession(payload: {
  purpose: string;
  requestedCredentialTypes: string[];
  requestedFields: string[];
  ttlSeconds?: number;
}): Promise<Oid4vpSession> {
  return parseSession(await apiRequest<unknown>("/api/v1/oid4vp/requests", {
    method: "POST",
    body: { ...payload, ttlSeconds: payload.ttlSeconds ?? 600 },
  }));
}

export async function getOid4vpSession(sessionId: string, signal?: AbortSignal): Promise<Oid4vpSession> {
  return parseSession(await apiRequest<unknown>(`/api/v1/oid4vp/requests/${encodeURIComponent(sessionId)}`, { signal }));
}

export async function getOid4vpHolderRequest(sessionId: string): Promise<Oid4vpHolderRequest> {
  const session = parseSession(
    await apiRequest<unknown>(`/api/v1/oid4vp/requests/${encodeURIComponent(sessionId)}/holder-request`),
  );
  const { verificationResult: _v, disclosedClaims: _d, rejectionReason: _r, ...request } = session;
  void _v; void _d; void _r;
  return request;
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

export async function evaluateOid4vpSession(
  sessionId: string,
  candidateCredentials: Record<string, unknown>[],
): Promise<Oid4vpDcqlEvaluation> {
  const body = await apiRequest<Oid4vpDcqlEvaluation>(
    `/api/v1/oid4vp/requests/${encodeURIComponent(sessionId)}/evaluate-dcql`,
    { method: "POST", body: { candidateCredentials } },
  );
  assertShape(typeof body?.isSatisfied === "boolean" && Array.isArray(body.matchedCredentials), "DCQL evaluation");
  return body;
}

export interface Oid4vpConsentResponse {
  sessionId: string;
  status: string;
  consentStatus: string;
  decisionId?: string;
  action: string;
  holderDid: string;
  approvedCredentials: string[];
  approvedClaims: Record<string, unknown>;
  rejectedClaims: string[];
  rejectionReason?: string;
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
  return apiRequest<Oid4vpConsentResponse>(
    `/api/v1/oid4vp/requests/${encodeURIComponent(payload.sessionId)}/wallet-consent`,
    {
      method: "POST",
      body: {
        walletId: payload.walletId,
        holderDid: payload.holderDid,
        action: payload.action,
        approvedCredentials: payload.approvedCredentials ?? [],
        approvedClaims: payload.approvedClaims ?? {},
        rejectedClaims: payload.rejectedClaims ?? [],
        rejectionReason: payload.rejectionReason,
      },
    },
  );
}

export async function createWalletOid4vpPresentation(payload: {
  sessionId: string;
  walletId: string;
  credentialIds: string[];
  disclosedClaims: Record<string, unknown>;
}): Promise<{ sessionId: string; vpToken: Record<string, unknown> }> {
  const body = await apiRequest<{ sessionId?: unknown; vpToken?: unknown }>("/api/v1/oid4vp/wallet-presentation", {
    method: "POST",
    body: payload,
  });
  assertShape(body && typeof body.vpToken === "object" && body.vpToken !== null, "presentation");
  return { sessionId: typeof body.sessionId === "string" ? body.sessionId : payload.sessionId, vpToken: body.vpToken as Record<string, unknown> };
}

/** Submit the prepared VP to the verifier's response endpoint (direct_post). */
export async function submitOid4vpDirectPost(payload: {
  sessionId: string;
  vpToken: Record<string, unknown>;
  disclosedClaims: Record<string, unknown>;
}): Promise<{ status: string; result: VerificationResult | null }> {
  const body = await apiRequest<{ status?: unknown; result?: unknown }>("/api/v1/oid4vp/response", {
    auth: "optional",
    method: "POST",
    body: payload,
  });
  return {
    status: typeof body?.status === "string" ? body.status : "UNKNOWN",
    result: parseVerificationResult(body?.result),
  };
}

export interface PresentationVerificationResult {
  verified: boolean;
  status: "VERIFIED" | "REJECTED" | "UNAVAILABLE" | "ERROR";
  /** Field names follow the existing frontend contract (tests/verifyPresentation_fail_closed). */
  signature_valid?: boolean;
  challenge_valid?: boolean;
  claims?: Record<string, unknown>;
  errors: string[];
  details?: unknown;
}

function claimsFrom(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

/**
 * Manual verification. Fail-closed: only an explicit backend
 * finalPolicyResult=ACCEPTED (or, for legacy bodies without a policy result,
 * valid=true) produces VERIFIED. Every failure path yields verified=false.
 */
export async function verifyPresentation(payload: Record<string, unknown>): Promise<PresentationVerificationResult> {
  let data: Record<string, unknown>;
  try {
    data = await apiRequest<Record<string, unknown>>("/api/v1/identity/presentations/verify", {
      auth: "optional",
      method: "POST",
      body: payload,
    });
  } catch (error) {
    if (isApiError(error)) {
      if (error.kind === "network" || error.kind === "timeout") {
        const detail = error.transportDetail ? ` (${error.transportDetail})` : "";
        return { verified: false, status: "UNAVAILABLE", errors: [`${error.message}${detail}`] };
      }
      if (error.status !== null && error.status >= 500) {
        return { verified: false, status: "ERROR", errors: [error.message] };
      }
      return { verified: false, status: "REJECTED", errors: [error.message] };
    }
    return { verified: false, status: "ERROR", errors: ["Verification could not be completed."] };
  }
  if (!data || typeof data !== "object") {
    return { verified: false, status: "ERROR", errors: ["The verifier returned an invalid response."] };
  }
  const result = data.result && typeof data.result === "object" ? data.result as Record<string, unknown> : null;
  const hasPolicy = Object.prototype.hasOwnProperty.call(data, "result");
  const verified = typeof result?.finalPolicyResult === "string"
    ? result.finalPolicyResult === "ACCEPTED"
    : hasPolicy ? false : data.valid === true || data.status === "VERIFIED";
  const errors = Array.isArray(data.errors)
    ? data.errors.filter((e): e is string => typeof e === "string")
    : Array.isArray(data.rejection_codes)
      ? data.rejection_codes.filter((e): e is string => typeof e === "string")
      : verified ? [] : ["Cryptographic or policy verification failed."];
  return {
    verified,
    status: verified ? "VERIFIED" : "REJECTED",
    signature_valid: typeof result?.signatureValid === "boolean" ? result.signatureValid : undefined,
    challenge_valid: typeof result?.challengeValid === "boolean" ? result.challengeValid : undefined,
    claims: claimsFrom(data.claims) ?? claimsFrom(data.disclosedClaims) ?? {},
    errors,
    details: data,
  };
}

export { ApiError };
