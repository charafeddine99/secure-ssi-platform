import { apiRequest, assertShape } from "../lib/http.ts";

/**
 * Wallet signing keys held by the platform's key custody (server-managed).
 * Only public metadata is returned by the API; private material never leaves
 * the key provider.
 */
export interface WalletKey {
  keyId: string;
  algorithm: string;
  purpose: string;
  keyVersion: number;
  state: string;
  provider: string;
  fingerprint: string | null;
  verificationMethod: string | null;
  createdAt: string;
  rotatedAt: string | null;
  revokedAt: string | null;
}

const optionalString = (value: unknown): string | null => (typeof value === "string" && value ? value : null);

/** GET /wallets/{walletId}/keys (ManagedKeyListResponse). Requires wallet:key:read. */
export function parseWalletKeys(value: unknown, walletId: string): WalletKey[] {
  const raw = (value ?? {}) as Record<string, unknown>;
  assertShape(raw.walletId === walletId && Array.isArray(raw.items), "wallet key list");
  return (raw.items as unknown[]).map((item, index) => {
    const key = (item ?? {}) as Record<string, unknown>;
    assertShape(
      typeof key.keyId === "string" && key.walletId === walletId
        && typeof key.algorithm === "string" && typeof key.purpose === "string"
        && typeof key.state === "string" && typeof key.keyVersion === "number"
        && typeof key.createdAt === "string",
      `wallet key at index ${index}`,
    );
    return {
      keyId: key.keyId as string,
      algorithm: key.algorithm as string,
      purpose: key.purpose as string,
      keyVersion: key.keyVersion as number,
      state: key.state as string,
      provider: typeof key.provider === "string" ? key.provider : "",
      fingerprint: optionalString(key.fingerprint),
      verificationMethod: optionalString(key.verificationMethod),
      createdAt: key.createdAt as string,
      rotatedAt: optionalString(key.rotatedAt),
      revokedAt: optionalString(key.revokedAt),
    };
  });
}

export async function fetchWalletKeys(walletId: string): Promise<WalletKey[]> {
  return parseWalletKeys(
    await apiRequest<unknown>(`/api/v1/identity/wallets/${encodeURIComponent(walletId)}/keys`),
    walletId,
  );
}
