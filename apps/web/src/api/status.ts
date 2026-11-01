import { apiRequest, assertShape } from "../lib/http.ts";
import { normalizeCredentialStatus, type CredentialStatus } from "./wallet.ts";

export interface CredentialStatusSnapshot {
  credentialId: string;
  status: CredentialStatus;
  revoked: boolean;
  revocationReason: string | null;
  revokedAt: string | null;
}

/**
 * The Identity Service serialises this response in camelCase. (WP-18: the
 * previous client read snake_case keys and therefore always reported an
 * "invalid response" for valid lookups.)
 */
export function parseCredentialStatus(value: unknown): CredentialStatusSnapshot {
  const raw = (value ?? {}) as Record<string, unknown>;
  const credentialId = raw.credentialId ?? raw.credential_id;
  assertShape(typeof credentialId === "string" && typeof raw.status === "string", "credential status");
  const reason = raw.revocationReason ?? raw.revocation_reason;
  const revokedAt = raw.revokedAt ?? raw.revoked_at;
  return {
    credentialId: credentialId as string,
    status: normalizeCredentialStatus(raw.status),
    revoked: raw.revoked === true,
    revocationReason: typeof reason === "string" ? reason : null,
    revokedAt: typeof revokedAt === "string" ? revokedAt : null,
  };
}

export interface CredentialStatusEvent {
  eventId: string;
  eventType: string;
  createdAt: string;
  /** Lifecycle metadata recorded with the event (for example the new status). */
  metadata: Record<string, unknown>;
}

export interface CredentialStatusHistory {
  credentialId: string;
  currentStatus: CredentialStatus;
  events: CredentialStatusEvent[];
}

/** GET /credentials/{id}/history (CredentialStatusHistoryResponse); oldest event first. */
export function parseCredentialHistory(value: unknown): CredentialStatusHistory {
  const raw = (value ?? {}) as Record<string, unknown>;
  assertShape(
    typeof raw.credentialId === "string" && typeof raw.currentStatus === "string" && Array.isArray(raw.events),
    "credential status history",
  );
  const events = (raw.events as unknown[]).map((item, index) => {
    const event = (item ?? {}) as Record<string, unknown>;
    assertShape(
      typeof event.eventId === "string" && typeof event.eventType === "string" && typeof event.createdAt === "string",
      `credential status event at index ${index}`,
    );
    return {
      eventId: event.eventId as string,
      eventType: event.eventType as string,
      createdAt: event.createdAt as string,
      metadata: event.metadata && typeof event.metadata === "object" ? event.metadata as Record<string, unknown> : {},
    };
  });
  events.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  return {
    credentialId: raw.credentialId as string,
    currentStatus: normalizeCredentialStatus(raw.currentStatus),
    events,
  };
}

/** Readable by the issuing authority and platform administrators only. */
export async function fetchCredentialHistory(credentialId: string): Promise<CredentialStatusHistory> {
  return parseCredentialHistory(
    await apiRequest<unknown>(`/api/v1/identity/credentials/${encodeURIComponent(credentialId)}/history`),
  );
}

export async function fetchCredentialStatus(credentialId: string): Promise<CredentialStatusSnapshot> {
  return parseCredentialStatus(
    await apiRequest<unknown>(`/api/v1/identity/credentials/${encodeURIComponent(credentialId)}/status`, { auth: "none" }),
  );
}

export async function revokeCredential(credentialId: string, reason: string): Promise<CredentialStatusSnapshot> {
  return parseCredentialStatus(
    await apiRequest<unknown>(`/api/v1/identity/credentials/${encodeURIComponent(credentialId)}/revoke`, {
      method: "POST",
      body: { reason },
    }),
  );
}
