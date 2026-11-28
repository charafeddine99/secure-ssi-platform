import { apiRequest, assertShape } from "../lib/http.ts";
import { assertSecurityKey, createSecurityKey } from "../lib/webauthnClient.ts";

export interface MfaStatus {
  required: boolean;
  enrolled: boolean;
  method: string | null;
}

const BASE = "/api/v1/identity/auth";

export async function fetchMfaStatus(): Promise<MfaStatus> {
  const body = await apiRequest<MfaStatus>(`${BASE}/mfa`);
  assertShape(body && typeof body.enrolled === "boolean" && typeof body.required === "boolean", "authenticator status");
  return body;
}

export async function beginTotpEnrollment(password: string, currentCode?: string): Promise<{ secret: string; otpauthUri: string }> {
  const body = await apiRequest<{ secret: string; otpauthUri: string }>(`${BASE}/mfa/totp`, {
    method: "POST",
    body: currentCode ? { password, currentCode } : { password },
  });
  assertShape(body && typeof body.secret === "string", "authenticator enrollment");
  return body;
}

export async function confirmTotpEnrollment(code: string): Promise<MfaStatus> {
  return apiRequest<MfaStatus>(`${BASE}/mfa/totp/confirm`, { method: "POST", body: { code } });
}

export async function requestStepUpToken(action: string, resource: string, code: string): Promise<string> {
  const body = await apiRequest<{ stepUpToken?: unknown }>(`${BASE}/step-up`, {
    method: "POST",
    body: { action, resource, code },
  });
  assertShape(typeof body?.stepUpToken === "string", "step-up token");
  return body.stepUpToken as string;
}

/** Sent only on the one request it was issued for, and never stored. */
export function stepUpHeaders(token: string | null | undefined): Record<string, string> {
  return token ? { "X-Step-Up-Token": token } : {};
}

export interface SecurityKeyStatus {
  configured: boolean;
  enrolled: boolean;
}

export function fetchSecurityKeyStatus(): Promise<SecurityKeyStatus> {
  return apiRequest<SecurityKeyStatus>(`${BASE}/webauthn`);
}

export async function registerSecurityKey(password: string): Promise<void> {
  const options = await apiRequest<Record<string, unknown>>(`${BASE}/webauthn/register/options`, { method: "POST", body: { password } });
  const credential = await createSecurityKey(options);
  await apiRequest<SecurityKeyStatus>(`${BASE}/webauthn/register/verify`, { method: "POST", body: { credential } });
}

export async function stepUpWithSecurityKey(action: string, resource: string): Promise<string> {
  const options = await apiRequest<Record<string, unknown>>(`${BASE}/webauthn/step-up/options`, { method: "POST", body: { action, resource } });
  const credential = await assertSecurityKey(options);
  const body = await apiRequest<{ stepUpToken?: unknown }>(`${BASE}/webauthn/step-up/verify`, { method: "POST", body: { action, resource, credential } });
  assertShape(typeof body?.stepUpToken === "string", "step-up token");
  return body.stepUpToken as string;
}

export async function changePassword(currentPassword: string, newPassword: string, stepUpToken?: string | null): Promise<void> {
  await apiRequest<unknown>(`${BASE}/password`, {
    method: "POST",
    headers: stepUpHeaders(stepUpToken),
    body: { currentPassword, newPassword },
  });
}
