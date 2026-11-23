import { apiRequest, assertShape } from "../lib/http.ts";

export interface ReissuanceRequest {
  requestId: string;
  credentialId: string;
  credentialType: string;
  issuerDid: string;
  oldHolderDid: string;
  newHolderDid: string;
  status: "PENDING" | "OFFERED" | "REJECTED" | string;
  createdAt: string;
  decidedAt: string | null;
  offerLink: string | null;
}

const BASE = "/api/v1/identity";

async function list(path: string): Promise<ReissuanceRequest[]> {
  const body = await apiRequest<{ items?: unknown }>(`${BASE}${path}`);
  assertShape(Array.isArray(body?.items), "re-issuance list");
  return body.items as ReissuanceRequest[];
}

export const fetchMyReissuanceRequests = () => list("/reissuance-requests/mine");
export const fetchIssuerReissuanceRequests = () => list("/reissuance-requests/issuer");

export function requestReissuance(walletId: string, credentialId: string): Promise<ReissuanceRequest> {
  return apiRequest<ReissuanceRequest>(`${BASE}/wallets/${encodeURIComponent(walletId)}/reissuance-requests`, {
    method: "POST",
    body: { credentialId },
  });
}

export function decideReissuance(requestId: string, decision: "approve" | "reject"): Promise<ReissuanceRequest> {
  return apiRequest<ReissuanceRequest>(`${BASE}/reissuance-requests/${encodeURIComponent(requestId)}/${decision}`, { method: "POST" });
}
