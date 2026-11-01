import { ApiError, apiRequest, assertShape } from "../lib/http.ts";

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
  credential_definition?: { "@context"?: string[]; type?: string[] };
  display?: Array<{ name?: string; locale?: string }>;
}

export interface Oid4vciIssuerMetadata {
  credential_issuer: string;
  credential_endpoint?: string;
  token_endpoint?: string;
  nonce_endpoint?: string;
  credential_configurations_supported: Record<string, Oid4vciCredentialConfiguration>;
}

function parseOffer(value: unknown): Oid4vciOffer {
  const raw = (value ?? {}) as Partial<Oid4vciOffer>;
  assertShape(
    typeof raw.offerId === "string" && typeof raw.preAuthorizedCode === "string" && Array.isArray(raw.credentialConfigurationIds),
    "credential offer",
  );
  return {
    offerId: raw.offerId as string,
    credentialIssuer: typeof raw.credentialIssuer === "string" ? raw.credentialIssuer : "",
    credentialConfigurationIds: raw.credentialConfigurationIds as string[],
    preAuthorizedCode: raw.preAuthorizedCode as string,
    status: typeof raw.status === "string" ? raw.status : "UNKNOWN",
    deepLinkUri: typeof raw.deepLinkUri === "string" ? raw.deepLinkUri : "",
    qrPayload: typeof raw.qrPayload === "string" ? raw.qrPayload : "",
    expiresAt: typeof raw.expiresAt === "string" ? raw.expiresAt : "",
    subjectData: raw.subjectData && typeof raw.subjectData === "object" ? raw.subjectData as Record<string, unknown> : {},
  };
}

export async function fetchOid4vciIssuerMetadata(signal?: AbortSignal): Promise<Oid4vciIssuerMetadata> {
  const value = await apiRequest<Partial<Oid4vciIssuerMetadata>>(
    "/api/v1/oid4vci/.well-known/openid-credential-issuer",
    { signal, timeoutMs: 10_000, auth: "none" },
  );
  assertShape(
    typeof value?.credential_issuer === "string"
      && value.credential_configurations_supported
      && typeof value.credential_configurations_supported === "object",
    "issuer metadata",
  );
  return value as Oid4vciIssuerMetadata;
}

export async function createOid4vciOffer(payload: {
  credentialConfigurationIds: string[];
  subjectData: Record<string, unknown>;
  recipientDid?: string;
  ttlSeconds?: number;
  userPin?: string;
}): Promise<Oid4vciOffer> {
  const body = await apiRequest<unknown>("/api/v1/oid4vci/offers", {
    method: "POST",
    body: {
      credentialConfigurationIds: payload.credentialConfigurationIds,
      subjectData: payload.subjectData,
      recipientDid: payload.recipientDid || undefined,
      ttlSeconds: payload.ttlSeconds ?? 1800,
      userPin: payload.userPin || undefined,
    },
  });
  return parseOffer(body);
}

export async function getOid4vciOffer(offerId: string): Promise<Oid4vciOffer> {
  // Only the issuing authority or the addressed holder may read an offer by id.
  return parseOffer(await apiRequest<unknown>(`/api/v1/oid4vci/offers/${encodeURIComponent(offerId)}`));
}

/** Offers addressed to the signed-in holder (holder DID or account binding). */
export async function fetchPendingOffers(): Promise<Oid4vciOffer[]> {
  const body = await apiRequest<unknown>("/api/v1/oid4vci/offers");
  assertShape(Array.isArray(body), "credential offer list");
  return (body as unknown[]).map(parseOffer);
}

/** Offers created by the signed-in issuer. This is not an issued-credential count. */
export async function fetchIssuerOffers(): Promise<Oid4vciOffer[]> {
  const body = await apiRequest<unknown>("/api/v1/oid4vci/offers?as_issuer=true");
  assertShape(Array.isArray(body), "issuer offer list");
  return (body as unknown[]).map(parseOffer);
}

export type IssuanceStep = "token" | "metadata" | "proof" | "credential";

export class IssuanceStepError extends ApiError {
  readonly step: IssuanceStep;

  constructor(step: IssuanceStep, cause: ApiError) {
    super(cause.kind, cause.message, cause.status, cause.code);
    this.step = step;
  }
}

async function runStep<T>(step: IssuanceStep, action: () => Promise<T>): Promise<T> {
  try {
    return await action();
  } catch (error) {
    if (error instanceof ApiError) throw new IssuanceStepError(step, error);
    throw error;
  }
}

/**
 * OID4VCI pre-authorized code flow, executed step by step:
 * token → issuer metadata → holder proof (server-managed key) → credential.
 * The credential endpoint is called with the OID4VCI access token, not the
 * session; the holder proof binds the credential to the wallet DID.
 */
export async function claimOid4vciOffer(payload: {
  preAuthorizedCode: string;
  walletId: string;
  holderDid: string;
  credentialConfigurationId: string;
  userPin?: string;
  onStep?: (step: IssuanceStep) => void;
}): Promise<{ credential: Record<string, unknown>; credentialId: string; status: string }> {
  payload.onStep?.("token");
  const form = new URLSearchParams({
    grant_type: "urn:ietf:params:oauth:grant-type:pre-authorized_code",
    "pre-authorized_code": payload.preAuthorizedCode,
  });
  if (payload.userPin) form.set("tx_code", payload.userPin);
  const token = await runStep("token", () =>
    apiRequest<{ access_token?: unknown; c_nonce?: unknown }>("/api/v1/oid4vci/token", { method: "POST", form, auth: "none" }),
  );
  if (typeof token.access_token !== "string" || typeof token.c_nonce !== "string") {
    throw new IssuanceStepError("token", new ApiError("schema", "The token endpoint returned an invalid response."));
  }

  payload.onStep?.("metadata");
  const metadata = await runStep("metadata", () => fetchOid4vciIssuerMetadata());

  payload.onStep?.("proof");
  const proof = await runStep("proof", () =>
    apiRequest<{ jwt?: unknown; holderDid?: unknown }>("/api/v1/oid4vci/holder-proof", {
      method: "POST",
      body: { walletId: payload.walletId, audience: metadata.credential_issuer, nonce: token.c_nonce },
    }),
  );
  if (typeof proof.jwt !== "string") {
    throw new IssuanceStepError("proof", new ApiError("schema", "The holder proof response was invalid."));
  }
  if (proof.holderDid !== payload.holderDid) {
    throw new IssuanceStepError("proof", new ApiError("conflict", "The signing wallet does not match the selected holder DID."));
  }

  payload.onStep?.("credential");
  const issued = await runStep("credential", () =>
    apiRequest<{ credential?: unknown; credentialId?: unknown; status?: unknown }>("/api/v1/oid4vci/credential", {
      method: "POST",
      headers: { Authorization: `Bearer ${token.access_token as string}` },
      body: {
        credentialConfigurationId: payload.credentialConfigurationId,
        proof: { proofType: "jwt", jwt: proof.jwt },
        walletId: payload.walletId,
      },
    }),
  );
  if (!issued.credential || typeof issued.credential !== "object") {
    throw new IssuanceStepError("credential", new ApiError("schema", "The credential endpoint returned no credential."));
  }
  const credential = issued.credential as Record<string, unknown>;
  const credentialId = typeof issued.credentialId === "string"
    ? issued.credentialId
    : typeof credential.id === "string" ? credential.id : "";
  if (!credentialId) {
    throw new IssuanceStepError("credential", new ApiError("schema", "The issued credential has no identifier."));
  }
  return { credential, credentialId, status: typeof issued.status === "string" ? issued.status : "UNKNOWN" };
}
