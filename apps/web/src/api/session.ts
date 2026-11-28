import { apiRequest, isApiError } from "../lib/http.ts";

export type AppRole = "HOLDER" | "ISSUER" | "VERIFIER" | "ADMIN";

export const IDENTITY_PERMISSIONS = [
  "auth:self:read",
  "credentials:revoke",
  "credentials:sign",
  "credentials:validate",
  "credentials:verify",
  "presentations:create",
  "presentations:read",
  "presentations:verify",
  "presentations:reconcile",
  "wallets:create",
  "wallets:read",
  "wallets:credentials:read",
  "wallets:backup",
  "wallets:restore",
  "presentation-challenges:create",
  "presentation-challenges:read",
  "wallet:key:create",
  "wallet:key:read",
  "wallet:key:rotate",
  "wallet:key:suspend",
  "wallet:key:resume",
  "wallet:key:compromise",
  "wallet:key:revoke",
  "wallet:key:destroy",
  "wallet:key:reconcile",
  "admin:key:reconcile",
  "admin:operations:read",
  "admin:users:read",
  "admin:users:write",
  "admin:backup:read",
  "admin:backup:write",
  "admin:incidents:write",
  "trust-registry:read",
  "trust-registry:write",
  "trust-review:decide",
] as const;

export type IdentityPermission = typeof IDENTITY_PERMISSIONS[number];

export interface SessionUser {
  id: string;
  username: string;
  displayName: string;
  role: AppRole;
  roles: string[];
  permissions: IdentityPermission[];
}

const ROLE_NAMES: Record<string, AppRole> = {
  admin: "ADMIN",
  issuer: "ISSUER",
  verifier: "VERIFIER",
  holder: "HOLDER",
};

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** Validate the backend user envelope; anything malformed is rejected. */
export function parseSessionUser(value: unknown): SessionUser | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  const id = text(raw.id);
  const username = text(raw.username);
  const displayName = text(raw.displayName) ?? text(raw.display_name);
  if (!id || !username || !displayName) return null;
  if (!Array.isArray(raw.roles) || !Array.isArray(raw.permissions)) return null;
  const roles = raw.roles.filter((role): role is string => typeof role === "string");
  const role = roles.map((name) => ROLE_NAMES[name.toLowerCase()]).find(Boolean);
  if (!role) return null;
  const known = new Set<string>(IDENTITY_PERMISSIONS);
  const permissions = [...new Set(raw.permissions.filter(
    (item): item is IdentityPermission => typeof item === "string" && known.has(item),
  ))];
  if (!permissions.includes("auth:self:read")) return null;
  return { id, username, displayName, role, roles, permissions };
}

export type SessionProfile = SessionUser & {
  /** Kept for the existing contract: never fabricated, filled only from a wallet lookup. */
  did: string;
  walletAddress: string;
};

export interface BackendAuthSession {
  /** Present only for API clients; the web app receives an HttpOnly cookie instead. */
  accessToken: string | null;
  user: SessionProfile;
}

const viteEnvironment = (import.meta as ImportMeta & {
  env?: { DEV?: boolean; VITE_ENABLE_DEMO_AUTH?: string };
}).env;

/** Demo credentials exist only in an explicitly enabled Vite development build. */
export const DEMO_AUTH_ENABLED =
  viteEnvironment?.DEV === true && viteEnvironment.VITE_ENABLE_DEMO_AUTH === "true";

export const DEMO_CREDENTIALS: Partial<Record<AppRole, { username: string; pass: string }>> = DEMO_AUTH_ENABLED
  ? {
      ADMIN: { username: "admin@example.test", pass: "Admin-Prototype-2026!" },
      ISSUER: { username: "issuer@example.test", pass: "Issuer-Prototype-2026!" },
      VERIFIER: { username: "verifier@example.test", pass: "Verifier-Prototype-2026!" },
      HOLDER: { username: "holder@example.test", pass: "Holder-Prototype-2026!" },
    }
  : {};

function toProfile(value: unknown): SessionProfile | null {
  const user = parseSessionUser(value);
  return user ? { ...user, did: "", walletAddress: "" } : null;
}

/**
 * POST /api/v1/identity/auth/token (existing contract). Returns null only for
 * HTTP 401; any other failure or malformed body throws.
 */
export async function authenticateBackend(username: string, password: string): Promise<BackendAuthSession | null> {
  let body: Record<string, unknown>;
  try {
    body = await apiRequest<Record<string, unknown>>("/api/v1/identity/auth/token", {
      method: "POST",
      body: { username: username.trim(), password },
      auth: "none",
      silentUnauthorized: true,
    });
  } catch (error) {
    if (isApiError(error) && error.status === 401) return null;
    if (isApiError(error) && error.status !== null) {
      throw new Error(`Identity Service rejected the sign-in request (HTTP ${error.status}).`);
    }
    throw error;
  }
  const accessToken = typeof body?.accessToken === "string" && body.accessToken.trim()
    ? body.accessToken.trim()
    : typeof body?.access_token === "string" && body.access_token.trim() ? body.access_token.trim() : null;
  const user = toProfile(body?.user);
  if (!user) throw new Error("Identity Service returned an invalid sign-in response.");
  return { accessToken, user };
}

/**
 * GET /api/v1/identity/auth/me. Without an argument the gateway session cookie
 * is used; an explicit token is sent as Bearer. An empty token sends nothing.
 */
export async function resolveBackendSession(token?: string): Promise<SessionProfile> {
  if (token !== undefined && !token.trim()) throw new Error("Identity Service rejected the access token (HTTP 401).");
  let body: unknown;
  try {
    body = await apiRequest<unknown>("/api/v1/identity/auth/me", { bearer: token, silentUnauthorized: true });
  } catch (error) {
    if (isApiError(error) && error.status !== null) {
      throw new Error(`Identity Service rejected the access token (HTTP ${error.status}).`);
    }
    throw error;
  }
  const user = toProfile(body);
  if (!user) throw new Error("Identity Service returned an invalid account profile.");
  return user;
}

/** POST /api/v1/identity/auth/revoke; the gateway also clears the session cookie. */
export async function revokeBackendToken(token?: string): Promise<void> {
  try {
    // "optional": sign-out clears the local marker first, and must still reach the gateway.
    await apiRequest<unknown>("/api/v1/identity/auth/revoke", { method: "POST", body: {}, bearer: token, auth: "optional", silentUnauthorized: true });
  } catch {
    throw new Error("Identity Service could not revoke the access token.");
  }
}
