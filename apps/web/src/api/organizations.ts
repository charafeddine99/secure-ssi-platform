import { apiRequest, assertShape } from "../lib/http.ts";
import { stepUpHeaders } from "./stepUp.ts";

/**
 * Organizations, memberships, invitations and capabilities. The server re-checks the membership on every
 * call; the organization id in the path only selects which one, and roles are never sent as authority.
 */
const BASE = "/api/v1/identity";

export const ORGANIZATION_TYPES = ["UNIVERSITY", "GOVERNMENT", "COMPANY", "NONPROFIT", "CERTIFICATION_BODY", "OTHER_INSTITUTION"] as const;
export const ORG_ROLES = ["ORG_ADMIN", "ISSUER_MANAGER", "ISSUER_OPERATOR", "VERIFIER_MANAGER", "VERIFIER_OPERATOR", "ORG_AUDITOR"] as const;
export type OrganizationType = typeof ORGANIZATION_TYPES[number];
export type OrgRole = typeof ORG_ROLES[number];
export const TRUST_REVIEW_ACTION = "trust-review.decide";

export interface Organization {
  organizationId: string;
  legalName: string;
  organizationType: OrganizationType;
  jurisdiction: string;
  registrationReference: string | null;
  officialDomain: string | null;
  website: string | null;
  status: "SUBMITTED" | "ACTIVE" | "REJECTED" | "SUSPENDED" | "REVOKED";
  requestedCapabilities: string[];
  createdAt: string;
}

export interface Membership {
  membershipId: string;
  userId: string;
  roles: OrgRole[];
  status: "PENDING" | "ACTIVE" | "REMOVED";
  acceptedAt: string | null;
}

export interface Invitation {
  invitationId: string;
  email: string;
  roles: OrgRole[];
  status: "OPEN" | "USED" | "REVOKED";
  expiresAt: string;
}

export interface Capability {
  capabilityId: string;
  organizationId: string;
  type: "ISSUER" | "VERIFIER";
  status: "PENDING" | "ACTIVE" | "REJECTED" | "SUSPENDED" | "REVOKED";
  credentialTypes: string[];
  purpose: string;
  issuerDid: string | null;
  clientId: string | null;
  redirectUris: string[] | null;
}

export interface OrganizationApplication {
  legalName: string;
  organizationType: OrganizationType;
  jurisdiction: string;
  registrationReference?: string;
  officialDomain?: string;
  website?: string;
  officialContact: string;
  applicantTitle: string;
  authorityEvidence: string;
  requestedCapabilities: ("ISSUER" | "VERIFIER")[];
  intendedUse: string;
}

export interface ReviewItem {
  organization: Organization;
  applicantUserId: string;
  applicantTitle: string;
  authorityEvidence: string;
  officialContact: string;
  intendedUse: string;
}

/** Empty optional fields are left out, so the server never sees "" as a value. */
function compact<T extends object>(value: T): T {
  return Object.fromEntries(Object.entries(value).filter(([, v]) => !(typeof v === "string" && v.trim() === ""))) as T;
}

export async function listMyOrganizations(): Promise<{ organization: Organization; membership: Membership }[]> {
  const body = await apiRequest<unknown>(`${BASE}/organizations/mine`);
  assertShape(Array.isArray(body), "organization list");
  return body as { organization: Organization; membership: Membership }[];
}

export const applyForOrganization = (application: OrganizationApplication) =>
  apiRequest<Organization>(`${BASE}/organizations/applications`, { method: "POST", body: compact(application) });

export const listMembers = (orgId: string) => apiRequest<Membership[]>(`${BASE}/organizations/${encodeURIComponent(orgId)}/members`);

export const changeMemberRoles = (orgId: string, membershipId: string, roles: OrgRole[]) =>
  apiRequest<Membership>(`${BASE}/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(membershipId)}/roles`, { method: "PUT", body: { roles } });

export const removeMember = (orgId: string, membershipId: string) =>
  apiRequest<unknown>(`${BASE}/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(membershipId)}`, { method: "DELETE" });

/** The code comes back once; give it to the person yourself. Only its digest is stored. */
export const inviteMember = (orgId: string, email: string, roles: OrgRole[]) =>
  apiRequest<{ invitation: Invitation; invitationCode: string }>(`${BASE}/organizations/${encodeURIComponent(orgId)}/invitations`, { method: "POST", body: { email: email.trim(), roles } });

export const listInvitations = (orgId: string) => apiRequest<Invitation[]>(`${BASE}/organizations/${encodeURIComponent(orgId)}/invitations`);

export const revokeInvitation = (orgId: string, invitationId: string) =>
  apiRequest<unknown>(`${BASE}/organizations/${encodeURIComponent(orgId)}/invitations/${encodeURIComponent(invitationId)}`, { method: "DELETE" });

export const acceptInvitation = (invitationCode: string) =>
  apiRequest<Membership>(`${BASE}/organization-invitations/accept`, { method: "POST", body: { invitationCode: invitationCode.trim() } });

export const listCapabilities = (orgId: string) => apiRequest<Capability[]>(`${BASE}/organizations/${encodeURIComponent(orgId)}/capabilities`);

export const requestCapability = (orgId: string, request: { type: "ISSUER" | "VERIFIER"; credentialTypes: string[]; purpose: string; issuerDid?: string; clientId?: string; redirectUris?: string[] }) =>
  apiRequest<Capability>(`${BASE}/organizations/${encodeURIComponent(orgId)}/capabilities`, { method: "POST", body: compact(request) });

export const reviewQueue = (status = "SUBMITTED") => apiRequest<ReviewItem[]>(`${BASE}/trust-review/organizations?status=${encodeURIComponent(status)}`);
export const capabilityQueue = (status = "PENDING") => apiRequest<Capability[]>(`${BASE}/trust-review/capabilities?status=${encodeURIComponent(status)}`);

export const decideOrganization = (orgId: string, decision: { decision: string; entityVerified: boolean; entityEvidence: string; representativeVerified: boolean; representativeEvidence: string; note: string }, token: string | null) =>
  apiRequest<Organization>(`${BASE}/trust-review/organizations/${encodeURIComponent(orgId)}/decision`, { method: "POST", body: decision, headers: stepUpHeaders(token) });

export const decideCapability = (capabilityId: string, decision: string, note: string, token: string | null) =>
  apiRequest<Capability>(`${BASE}/trust-review/capabilities/${encodeURIComponent(capabilityId)}/decision`, { method: "POST", body: { decision, note }, headers: stepUpHeaders(token) });
