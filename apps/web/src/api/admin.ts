import { apiRequest, assertShape } from "../lib/http.ts";

/* ---------- Trust Registry ---------- */

export interface TrustRecord {
  id: string;
  issuerDid: string;
  organizationName: string;
  trustStatus: string;
  trustSource?: string;
  roles: string[];
  permittedCredentialTypes: string[];
  validFrom: string;
  validUntil?: string | null;
  version?: number;
}

function stringList(value: unknown): string[] | null {
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value as string[] : null;
}

export function parseTrustRecord(value: unknown, index = 0): TrustRecord {
  assertShape(value && typeof value === "object" && !Array.isArray(value), `trust record at index ${index}`);
  const raw = value as Record<string, unknown>;
  const read = (camel: string, snake = camel): unknown => raw[camel] ?? raw[snake];
  const required = (camel: string, snake = camel): string => {
    const field = read(camel, snake);
    assertShape(typeof field === "string" && field.trim(), `trust record (${camel}) at index ${index}`);
    return field as string;
  };
  const roles = stringList(read("roles"));
  const types = stringList(read("permittedCredentialTypes", "permitted_credential_types"));
  assertShape(roles && types, `trust record lists at index ${index}`);
  const validUntil = read("validUntil", "valid_until");
  assertShape(validUntil === undefined || validUntil === null || typeof validUntil === "string", `trust record validity at index ${index}`);
  const trustSource = read("trustSource", "trust_source");
  return {
    id: required("id"),
    issuerDid: required("issuerDid", "issuer_did"),
    organizationName: required("organizationName", "organization_name"),
    trustStatus: required("trustStatus", "trust_status"),
    trustSource: typeof trustSource === "string" ? trustSource : undefined,
    roles: roles as string[],
    permittedCredentialTypes: types as string[],
    validFrom: required("validFrom", "valid_from"),
    validUntil: validUntil as string | null | undefined,
    version: typeof raw.version === "number" ? raw.version : undefined,
  };
}

export async function fetchPublicTrustedIssuers(signal?: AbortSignal): Promise<TrustRecord[]> {
  const body = await apiRequest<unknown>("/api/v1/identity/trust-registry/issuers?limit=100", { signal, timeoutMs: 10_000, auth: "none" });
  assertShape(Array.isArray(body), "trust registry list");
  return (body as unknown[]).map(parseTrustRecord);
}

export async function registerTrustedIssuer(payload: {
  issuerDid: string;
  organizationName: string;
  permittedCredentialTypes: string[];
  validDays: number;
}): Promise<TrustRecord> {
  return parseTrustRecord(await apiRequest<unknown>("/api/v1/identity/trust-registry/issuers", {
    method: "POST",
    body: { ...payload, roles: ["issuer"] },
  }));
}

export async function changeTrustStatus(recordId: string, action: "suspend" | "revoke", reason: string): Promise<TrustRecord> {
  return parseTrustRecord(await apiRequest<unknown>(
    `/api/v1/identity/trust-registry/issuers/${encodeURIComponent(recordId)}/${action}`,
    { method: "POST", body: { reason } },
  ));
}

/* ---------- Audit & persistence ---------- */

export interface AuditLogEntry {
  id: string;
  eventType: string;
  actorDid: string;
  targetWallet: string | null;
  riskScore: number | null;
  details: Record<string, unknown>;
  createdAt: string;
}

export async function fetchAuditLogs(eventType?: string, limit = 100): Promise<AuditLogEntry[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (eventType && eventType !== "ALL") query.set("event_type", eventType);
  const body = await apiRequest<{ audit_logs?: unknown; events?: unknown }>(`/api/v1/identity/audit_logs?${query.toString()}`);
  const rows = body?.audit_logs ?? body?.events;
  assertShape(Array.isArray(rows), "audit event list");
  return (rows as Record<string, unknown>[]).map((row) => ({
    id: String(row.id ?? ""),
    eventType: typeof row.event_type === "string" ? row.event_type : "UNKNOWN",
    actorDid: typeof row.actor_did === "string" ? row.actor_did : "",
    targetWallet: typeof row.target_wallet === "string" ? row.target_wallet : null,
    riskScore: typeof row.risk_score === "number" ? row.risk_score : null,
    details: row.details && typeof row.details === "object" ? row.details as Record<string, unknown> : {},
    createdAt: typeof row.created_at === "string" ? row.created_at : "",
  }));
}

export interface DatabaseStats {
  authoritativePersistence: string;
  counts: Record<string, number>;
}

export async function fetchDatabaseStats(): Promise<DatabaseStats> {
  const body = await apiRequest<Record<string, unknown>>("/api/v1/identity/database/stats");
  const stats = body?.stats;
  assertShape(stats && typeof stats === "object", "persistence statistics");
  const counts: Record<string, number> = {};
  for (const [key, value] of Object.entries(stats as Record<string, unknown>)) {
    if (typeof value === "number") counts[key] = value;
  }
  return {
    authoritativePersistence: typeof body.authoritative_persistence === "string" ? body.authoritative_persistence : "UNKNOWN",
    counts,
  };
}

/* ---------- Users ---------- */

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

export async function fetchAdminUsers(): Promise<AdminUserRecord[]> {
  const body = await apiRequest<unknown>("/api/v1/identity/admin/users");
  assertShape(Array.isArray(body), "user list");
  return body as AdminUserRecord[];
}

export async function fetchAdminIssuerScopeOptions(): Promise<AdminIssuerScopeOption[]> {
  const body = await apiRequest<unknown>("/api/v1/identity/admin/users/issuer-options");
  assertShape(Array.isArray(body), "issuer option list");
  return body as AdminIssuerScopeOption[];
}

export async function updateAdminIssuerScope(userId: string, issuerDid: string | null, expectedVersion: number): Promise<AdminUserRecord> {
  return apiRequest<AdminUserRecord>(`/api/v1/identity/admin/users/${encodeURIComponent(userId)}/issuer-scope`, {
    method: "PUT",
    body: { issuerDid, expectedVersion },
  });
}

/* ---------- Optional anchoring ---------- */

export interface BlockchainStatus {
  connected: boolean;
  network: string;
  chainId: number | null;
  currentBlockNumber: number | null;
  contracts: Record<string, string>;
}

export async function fetchBlockchainStatus(): Promise<BlockchainStatus> {
  const body = await apiRequest<Record<string, unknown>>("/api/v1/blockchain/status", { auth: "optional" });
  assertShape(body && typeof body.connected === "boolean", "blockchain status");
  return {
    connected: body.connected as boolean,
    network: typeof body.network === "string" ? body.network : "unknown",
    chainId: typeof body.chainId === "number" ? body.chainId : null,
    currentBlockNumber: typeof body.currentBlockNumber === "number" ? body.currentBlockNumber : null,
    contracts: body.contracts && typeof body.contracts === "object" ? body.contracts as Record<string, string> : {},
  };
}

export interface SmartContractInfo {
  name: string;
  address: string;
  purpose: string;
  methods: string[];
  status: string;
  deploymentVerified?: boolean | null;
}

export async function fetchBlockchainContracts(): Promise<SmartContractInfo[]> {
  const body = await apiRequest<{ contracts?: unknown }>("/api/v1/blockchain/contracts", { auth: "optional" });
  assertShape(Array.isArray(body?.contracts), "contract directory");
  return body.contracts as SmartContractInfo[];
}

export interface OnChainAnchor {
  anchorId: string;
  eventType: string;
  eventHash: string;
  contractType: string;
  status: string;
  createdAt: string;
  txHash?: string;
  blockNumber?: number;
  errorMessage?: string;
}

export async function fetchBlockchainAnchors(limit = 20): Promise<OnChainAnchor[]> {
  const body = await apiRequest<unknown>(`/api/v1/blockchain/anchors?limit=${limit}`, { auth: "optional" });
  assertShape(Array.isArray(body), "anchor list");
  return body as OnChainAnchor[];
}

/* ---------- Platform health & advisory risk ---------- */

export interface GatewayStatus {
  gatewayStatus: string;
  systemHealth: string;
  services: Record<string, string>;
}

export async function fetchGatewayStatus(): Promise<GatewayStatus> {
  const body = await apiRequest<Record<string, unknown>>("/api/v1/system/status", { auth: "optional" });
  assertShape(body && typeof body.services === "object" && body.services !== null, "platform status");
  return {
    gatewayStatus: typeof body.gateway_status === "string" ? body.gateway_status : "UNKNOWN",
    systemHealth: typeof body.system_health === "string" ? body.system_health : "UNKNOWN",
    services: body.services as Record<string, string>,
  };
}

export interface FraudModelStats {
  model_type: string;
  model_version: string;
  model_status: string;
  evaluation_status: string;
  dataset_label: string;
  advisory_only: boolean;
  risk_signals: string[];
}

export async function fetchFraudStats(): Promise<FraudModelStats> {
  const body = await apiRequest<FraudModelStats>("/api/v1/fraud/stats");
  assertShape(body && typeof body.model_version === "string" && typeof body.model_status === "string", "risk engine status");
  return body;
}
