import { apiRequest, assertShape, isApiError } from "../lib/http.ts";
import { clearCachedWalletId, readCachedWalletId, storeCachedWalletId } from "../lib/tokenStore.ts";

export type CredentialStatus = "ACTIVE" | "SUSPENDED" | "REVOKED" | "EXPIRED" | "UNKNOWN";

export interface HolderWallet {
  walletId: string;
  holderDid: string;
  status: string;
  ownerUserId: string;
}

export interface WalletCredential {
  id: string;
  holderDid: string;
  type: string;
  types: string[];
  issuer: string;
  validFrom: string;
  validUntil: string;
  status: CredentialStatus;
  claims: Record<string, unknown>;
  proofType: string;
  cryptosuite: string;
  statusListId?: string;
  statusListIndex?: number;
  raw: Record<string, unknown>;
}

interface RawWallet {
  walletId?: unknown;
  holderDid?: unknown;
  status?: unknown;
  ownerUserId?: unknown;
}

function parseWallet(value: unknown): HolderWallet {
  const raw = (value ?? {}) as RawWallet;
  assertShape(typeof raw.walletId === "string" && typeof raw.holderDid === "string", "holder wallet");
  return {
    walletId: raw.walletId as string,
    holderDid: raw.holderDid as string,
    status: typeof raw.status === "string" ? raw.status : "UNKNOWN",
    ownerUserId: typeof raw.ownerUserId === "string" ? raw.ownerUserId : "",
  };
}

/**
 * Resolve or create the signed-in user's server-managed wallet using the
 * existing contract: GET /auth/me → cached wallet ID (per account, same
 * localStorage key as before) → GET /wallets/{id} → otherwise POST /wallets.
 * NOTE: there is no owner-scoped wallet listing in the current API, so a new
 * browser may create an additional wallet (see FRONTEND_BACKEND_HANDOFF.md).
 */
export async function getOrCreateHolderWallet(): Promise<HolderWallet> {
  const me = await apiRequest<{ id?: unknown }>("/api/v1/identity/auth/me");
  assertShape(typeof me?.id === "string" && me.id, "account profile");
  const userId = me.id as string;
  const cached = readCachedWalletId(userId);
  if (cached) {
    try {
      return parseWallet(await apiRequest<unknown>(`/api/v1/identity/wallets/${encodeURIComponent(cached)}`));
    } catch (error) {
      if (!(isApiError(error) && error.kind === "not_found")) throw error;
      clearCachedWalletId(userId);
    }
  }
  const created = parseWallet(await apiRequest<unknown>("/api/v1/identity/wallets", { method: "POST", body: {} }));
  storeCachedWalletId(userId, created.walletId);
  return created;
}

export function normalizeCredentialStatus(status: unknown): CredentialStatus {
  if (typeof status !== "string") return "UNKNOWN";
  const upper = status.toUpperCase();
  return ["ACTIVE", "SUSPENDED", "REVOKED", "EXPIRED"].includes(upper)
    ? upper as CredentialStatus
    : "UNKNOWN";
}

interface RawWalletCredential {
  credentialId?: string;
  holderDid?: string;
  status?: string;
  issuanceDate?: string;
  expirationDate?: string;
  statusListId?: string;
  statusListIndex?: number;
  credential?: Record<string, unknown>;
}

export function mapWalletCredential(item: RawWalletCredential): WalletCredential | null {
  const raw = item.credential && typeof item.credential === "object" ? item.credential : {};
  const subject = raw.credentialSubject && typeof raw.credentialSubject === "object" && !Array.isArray(raw.credentialSubject)
    ? { ...(raw.credentialSubject as Record<string, unknown>) }
    : {};
  const holderDid = typeof subject.id === "string" ? subject.id : item.holderDid ?? "";
  delete subject.id;
  const types = Array.isArray(raw.type) ? raw.type.filter((t): t is string => typeof t === "string") : [];
  const issuerValue = raw.issuer;
  const issuer = typeof issuerValue === "string"
    ? issuerValue
    : issuerValue && typeof issuerValue === "object" && typeof (issuerValue as { id?: unknown }).id === "string"
      ? (issuerValue as { id: string }).id
      : "";
  const proof = raw.proof && typeof raw.proof === "object" ? raw.proof as Record<string, unknown> : {};
  const id = item.credentialId || (typeof raw.id === "string" ? raw.id : "");
  if (!id) return null;
  return {
    id,
    holderDid,
    type: types.find((t) => t !== "VerifiableCredential") ?? "VerifiableCredential",
    types,
    issuer,
    validFrom: typeof raw.validFrom === "string" ? raw.validFrom : item.issuanceDate ?? "",
    validUntil: typeof raw.validUntil === "string" ? raw.validUntil : item.expirationDate ?? "",
    status: normalizeCredentialStatus(item.status),
    claims: subject,
    proofType: typeof proof.type === "string" ? proof.type : "",
    cryptosuite: typeof proof.cryptosuite === "string" ? proof.cryptosuite : "",
    statusListId: item.statusListId,
    statusListIndex: item.statusListIndex,
    raw,
  };
}

/** Owner-bound credential inventory; errors are thrown, never returned as []. */
export async function fetchWalletCredentials(walletId: string): Promise<WalletCredential[]> {
  const body = await apiRequest<{ credentials?: unknown }>(
    `/api/v1/identity/wallets/${encodeURIComponent(walletId)}/credentials`,
  );
  assertShape(Array.isArray(body?.credentials), "credential inventory");
  return (body.credentials as RawWalletCredential[])
    .map(mapWalletCredential)
    .filter((item): item is WalletCredential => item !== null);
}

/**
 * Existing contract (tests/verifyPresentation_fail_closed): credential
 * inventory for a wallet; the first two legacy parameters are ignored and a
 * missing status stays "UNKNOWN".
 */
export async function fetchCredentials(
  _userDid?: string,
  _walletAddress?: string,
  walletId?: string,
): Promise<WalletCredential[]> {
  void _userDid;
  void _walletAddress;
  const id = walletId ?? (await getOrCreateHolderWallet()).walletId;
  return fetchWalletCredentials(id);
}
