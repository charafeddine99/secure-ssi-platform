import { apiRequest, assertShape } from "../lib/http.ts";
import { stepUpHeaders } from "./stepUp.ts";

export interface BackupCollection {
  name: string;
  documents: number;
  indexes: string[];
}

export interface PlatformBackup {
  backupId: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED" | "EXPIRED" | string;
  sourceDatabase: string;
  createdBy: string;
  startedAt: string;
  finishedAt: string | null;
  durationMs: number | null;
  sizeBytes: number | null;
  archiveSha256: string | null;
  schemaVersion: number;
  appVersion: string;
  consistency: string;
  completeness: string;
  components: string[];
  watermark: string | null;
  encryption: string;
  collections: BackupCollection[];
  expiresAt: string | null;
  failureCode: string | null;
  lastVerifiedAt: string | null;
  lastVerifyResult: string | null;
}

export interface PlatformBackupList {
  enabled: boolean;
  disabledReason: string | null;
  retentionSeconds: number;
  scheduler: string;
  intervalSeconds: number;
  offsite: string;
  immutable: string;
  pointInTime: string;
  keyCustody: string;
  scope: string[];
  restoreExecution: string;
  items: PlatformBackup[];
}

export interface PlatformRestorePreview {
  backup: PlatformBackup;
  targetDatabase: string;
  targetNameAccepted: boolean;
  schemaCompatible: boolean;
  integrityVerified: boolean;
  executionAvailable: boolean;
  collections: BackupCollection[];
  blockingReasons: string[];
}

const BASE = "/api/v1/identity/admin/platform-backups";

export async function fetchPlatformBackups(): Promise<PlatformBackupList> {
  const body = await apiRequest<PlatformBackupList>(BASE);
  assertShape(body && typeof body.enabled === "boolean" && Array.isArray(body.items), "platform backup list");
  return body;
}

export async function createPlatformBackup(stepUpToken: string | null): Promise<PlatformBackup> {
  const body = await apiRequest<PlatformBackup>(BASE, { method: "POST", timeoutMs: 120_000, headers: stepUpHeaders(stepUpToken) });
  assertShape(body && typeof body.backupId === "string", "platform backup");
  return body;
}

export async function verifyPlatformBackup(backupId: string): Promise<PlatformBackup> {
  const body = await apiRequest<{ backup?: PlatformBackup; integrityVerified?: boolean }>(
    `${BASE}/${encodeURIComponent(backupId)}/verify`,
    { method: "POST", timeoutMs: 120_000 },
  );
  assertShape(body?.backup && body.integrityVerified === true, "backup verification");
  return body.backup;
}

export async function previewPlatformRestore(backupId: string, targetDatabase: string): Promise<PlatformRestorePreview> {
  const body = await apiRequest<PlatformRestorePreview>(`${BASE}/${encodeURIComponent(backupId)}/restore-preview`, {
    method: "POST",
    body: { targetDatabase },
    timeoutMs: 120_000,
  });
  assertShape(body && typeof body.targetNameAccepted === "boolean" && Array.isArray(body.blockingReasons), "restore preview");
  return body;
}

export interface ReadinessReport {
  environment: string;
  ready: boolean;
  blockers: string[];
  warnings: string[];
  details: {
    keyCustody?: { issuer?: string; liveKms?: string };
    ledger?: { protection?: string; sequence?: number };
    backup?: { offsite?: string; immutable?: string; pointInTime?: string; lastVerifiedRestorePoint?: string | null };
  };
}

export async function fetchReadiness(): Promise<ReadinessReport> {
  const body = await apiRequest<ReadinessReport>("/api/v1/identity/admin/readiness");
  assertShape(body && typeof body.ready === "boolean" && Array.isArray(body.blockers), "readiness report");
  return body;
}

export interface DualControlOperation {
  operationId: string;
  operationType: string;
  target: string;
  requestedBy: string;
  approvedBy: string | null;
  status: string;
  expiresAt: string;
}

const DUAL = "/api/v1/identity/admin/dual-control";

export async function fetchDualControl(): Promise<DualControlOperation[]> {
  const body = await apiRequest<{ items?: unknown }>(DUAL);
  assertShape(Array.isArray(body?.items), "approval list");
  return body.items as DualControlOperation[];
}

export async function requestDualControl(
  operationType: string,
  target: string,
  reason: string,
  stepUpToken?: string | null,
): Promise<DualControlOperation> {
  return apiRequest<DualControlOperation>(DUAL, {
    method: "POST",
    headers: stepUpHeaders(stepUpToken),
    body: { operationType, target, reason },
  });
}

export async function approveDualControl(
  operationId: string,
  stepUpToken?: string | null,
): Promise<{ operation: DualControlOperation; executionToken: string }> {
  const body = await apiRequest<{ operation: DualControlOperation; executionToken: string }>(
    `${DUAL}/${encodeURIComponent(operationId)}/approve`,
    { method: "POST", headers: stepUpHeaders(stepUpToken) },
  );
  assertShape(typeof body?.executionToken === "string", "approval");
  return body;
}
