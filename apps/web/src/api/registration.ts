import { apiRequest, assertShape } from "../lib/http.ts";
import { stepUpHeaders } from "./stepUp.ts";

export type RegistrationRole = "holder" | "issuer" | "verifier" | "admin";

export interface RegistrationInput {
  email: string;
  displayName: string;
  password: string;
  role: RegistrationRole;
  organization?: string;
  purpose?: string;
  invitationCode?: string;
}

export interface OnboardingItem {
  requestId: string;
  email: string;
  displayName: string;
  role: string;
  organization: string;
  purpose: string;
  status: string;
  createdAt: string;
}

export async function registerAccount(input: RegistrationInput): Promise<string> {
  const body = await apiRequest<{ message?: unknown }>("/api/v1/identity/auth/register", {
    method: "POST",
    body: input,
    auth: "none",
  });
  assertShape(typeof body?.message === "string", "registration response");
  return body.message as string;
}

export async function fetchOnboardingRequests(): Promise<OnboardingItem[]> {
  const body = await apiRequest<OnboardingItem[]>("/api/v1/identity/admin/onboarding");
  assertShape(Array.isArray(body), "onboarding list");
  return body;
}

export function decideOnboarding(requestId: string, decision: "approve" | "reject", note: string, stepUpToken: string | null): Promise<OnboardingItem> {
  return apiRequest<OnboardingItem>(`/api/v1/identity/admin/onboarding/${encodeURIComponent(requestId)}/${decision}`, {
    method: "POST",
    body: { note },
    headers: stepUpHeaders(stepUpToken),
  });
}

export async function inviteAdministrator(email: string, stepUpToken: string | null): Promise<string> {
  const body = await apiRequest<{ invitationCode?: unknown }>("/api/v1/identity/admin/invitations", {
    method: "POST",
    body: { email },
    headers: stepUpHeaders(stepUpToken),
  });
  assertShape(typeof body?.invitationCode === "string", "invitation");
  return body.invitationCode as string;
}
