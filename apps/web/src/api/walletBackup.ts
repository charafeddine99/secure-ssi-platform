import { apiRequest, assertShape } from "../lib/http.ts";
import { stepUpHeaders } from "./stepUp.ts";

/** Identity Service WP-28 wallet backup contract (camelCase JSON). */
export interface WalletBackup {
  backupId: string;
  walletId: string;
  holderDid: string;
  formatVersion: number;
  itemCount: number;
  contentDigest: string;
  createdAt: string;
}

export type RestoreOutcome =
  | "RESTORABLE" | "ALREADY_PRESENT" | "HELD_BY_ANOTHER_WALLET" | "HOLDER_BINDING_MISMATCH"
  | "PROOF_INVALID" | "REVOKED" | "STATUS_UNVERIFIABLE" | "UNSUPPORTED_ITEM"
  | "RESTORED" | "NOT_ATTEMPTED";

export interface RestoreItem {
  credentialId: string;
  outcome: RestoreOutcome | string;
  credentialTypes: string[];
}

export interface RestorePreview {
  backup: WalletBackup;
  total: number;
  restorable: number;
  alreadyPresent: number;
  notRestorable: number;
  items: RestoreItem[];
}

export interface RestoreJob {
  restoreId: string;
  backupId: string;
  walletId: string;
  status: "COMPLETED" | "PARTIAL" | "FAILED" | string;
  restored: number;
  alreadyPresent: number;
  rejected: number;
  failureCode: string | null;
  items: RestoreItem[];
  createdAt: string;
}

const base = (walletId: string) => `/api/v1/identity/wallets/${encodeURIComponent(walletId)}`;

function isBackup(value: unknown): value is WalletBackup {
  const raw = value as Partial<WalletBackup> | null;
  return Boolean(raw && typeof raw.backupId === "string" && typeof raw.walletId === "string"
    && typeof raw.itemCount === "number" && typeof raw.createdAt === "string");
}

export async function listWalletBackups(walletId: string): Promise<WalletBackup[]> {
  const body = await apiRequest<{ items?: unknown }>(`${base(walletId)}/backups`);
  assertShape(Array.isArray(body?.items) && body.items.every(isBackup), "wallet backup list");
  return body.items as WalletBackup[];
}

/** The payload is plaintext for client-side encryption only; callers must not store it. */
export async function createWalletBackup(walletId: string, stepUpToken?: string | null): Promise<{ backup: WalletBackup; payload: string }> {
  const body = await apiRequest<{ backup?: unknown; payload?: unknown }>(`${base(walletId)}/backups`, { method: "POST", headers: stepUpHeaders(stepUpToken) });
  assertShape(
    isBackup(body?.backup) && body.backup.walletId === walletId && typeof body.payload === "string",
    "wallet backup",
  );
  return { backup: body.backup as WalletBackup, payload: body.payload as string };
}

export async function previewWalletRestore(walletId: string, backupId: string, payload: string): Promise<RestorePreview> {
  const body = await apiRequest<RestorePreview>(`${base(walletId)}/backups/${encodeURIComponent(backupId)}/preview`, {
    method: "POST",
    body: { payload },
  });
  assertShape(body && isBackup(body.backup) && Array.isArray(body.items), "restore preview");
  return body;
}

export async function restoreWalletBackup(
  walletId: string,
  backupId: string,
  payload: string,
  idempotencyKey: string,
  stepUpToken?: string | null,
): Promise<RestoreJob> {
  const body = await apiRequest<RestoreJob>(`${base(walletId)}/backups/${encodeURIComponent(backupId)}/restore`, {
    method: "POST",
    body: { payload },
    headers: { "Idempotency-Key": idempotencyKey, ...stepUpHeaders(stepUpToken) },
    timeoutMs: 60_000,
  });
  assertShape(body && typeof body.restoreId === "string" && Array.isArray(body.items), "restore job");
  return body;
}
