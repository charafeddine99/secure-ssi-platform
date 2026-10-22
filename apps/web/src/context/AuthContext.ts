import { createContext, useContext } from "react";

export interface UserProfile {
  name: string;
  nationalId: string;
  email: string;
  organization: string;
  did: string;
  walletAddress: string;
  assuranceLevel: "UNASSESSED" | "LOW" | "SUBSTANTIAL" | "HIGH";
  role: "HOLDER" | "ISSUER" | "VERIFIER" | "ADMIN";
  permissions: IdentityPermission[];
  studentId?: string;
  department?: string;
}

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
  "trust-registry:read",
  "trust-registry:write"
] as const;

export type IdentityPermission = typeof IDENTITY_PERMISSIONS[number];

export interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  isDemoEvaluationMode: boolean;
  setDemoEvaluationMode: (enabled: boolean) => void;
  switchDemoRole: (role: UserProfile["role"]) => Promise<boolean>;
  login: (email: string, pass: string) => Promise<boolean>;
  loginWithMetaMask: () => Promise<boolean>;
  register: (
    name: string,
    nationalId: string,
    email: string,
    organization: string,
    password?: string
  ) => { user: UserProfile; seedPhrase: string };
  logout: () => void;
  quickDemoLogin: () => Promise<boolean>;
}

const viteEnvironment = (import.meta as ImportMeta & {
  env?: { DEV?: boolean; VITE_ENABLE_DEMO_AUTH?: string; VITE_API_BASE_URL?: string };
}).env;

/** Demo credentials are available only in an explicitly enabled Vite dev build. */
export const DEMO_AUTH_ENABLED =
  viteEnvironment?.DEV === true && viteEnvironment.VITE_ENABLE_DEMO_AUTH === "true";

const gatewayBaseUrl = viteEnvironment?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const identityAuthEndpoints = [
  `${gatewayBaseUrl}/api/v1/identity/auth`,
  ...(viteEnvironment?.DEV === true
    ? ["http://127.0.0.1:8001/api/v1/auth"]
    : [])
];

export const DEMO_CREDENTIALS: Partial<
  Record<UserProfile["role"], { username: string; pass: string }>
> = DEMO_AUTH_ENABLED
  ? {
      ADMIN: { username: "admin@example.test", pass: "Admin-Prototype-2026!" },
      ISSUER: { username: "issuer@example.test", pass: "Issuer-Prototype-2026!" },
      VERIFIER: { username: "verifier@example.test", pass: "Verifier-Prototype-2026!" },
      HOLDER: { username: "holder@example.test", pass: "Holder-Prototype-2026!" }
    }
  : {};

interface BackendUser {
  id: string;
  username: string;
  displayName: string;
  roles: string[];
  permissions: string[];
}

export interface BackendAuthSession {
  accessToken: string;
  user: UserProfile;
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function normalizeBackendUser(value: unknown): BackendUser | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const id = readString(raw.id);
  const username = readString(raw.username);
  const displayName = readString(raw.displayName) ?? readString(raw.display_name);
  const rolesValue = raw.roles;
  const permissionsValue = raw.permissions;
  if (
    !id || !username || !displayName ||
    !Array.isArray(rolesValue) || !Array.isArray(permissionsValue)
  ) return null;
  const roles = rolesValue.filter((role): role is string => typeof role === "string");
  const permissions = permissionsValue.filter(
    (permission): permission is string => typeof permission === "string"
  );
  return roles.length ? { id, username, displayName, roles, permissions } : null;
}

function profileFromBackendUser(value: unknown): UserProfile | null {
  const user = normalizeBackendUser(value);
  if (!user) return null;
  const roleNames: Record<string, UserProfile["role"]> = {
    admin: "ADMIN",
    issuer: "ISSUER",
    verifier: "VERIFIER",
    holder: "HOLDER",
  };
  const role = user.roles.map((item) => roleNames[item.toLowerCase()]).find(Boolean);
  if (!role) return null;
  const knownPermissions = new Set<string>(IDENTITY_PERMISSIONS);
  const permissions = [...new Set(
    user.permissions.filter(
      (permission): permission is IdentityPermission => knownPermissions.has(permission),
    ),
  )];
  if (!permissions.includes("auth:self:read")) return null;

  return {
    name: user.displayName,
    nationalId: "NOT_ASSESSED",
    email: user.username,
    organization: "Not provided by the Identity Service",
    did: "",
    walletAddress: "",
    assuranceLevel: "UNASSESSED",
    role,
    permissions
  };
}

async function requestFromIdentity(path: string, init: RequestInit): Promise<Response> {
  let unavailable = false;
  for (const base of identityAuthEndpoints) {
    try {
      const response = await fetch(`${base}${path}`, init);
      if ([404, 502, 503].includes(response.status)) {
        unavailable = true;
        continue;
      }
      return response;
    } catch {
      unavailable = true;
    }
  }
  if (unavailable) throw new Error("Identity Service is unavailable.");
  throw new Error("Identity Service request failed.");
}

export async function authenticateBackend(
  username: string,
  password: string
): Promise<BackendAuthSession | null> {
  const response = await requestFromIdentity("/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username.trim(), password })
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(`Identity Service rejected the sign-in request (HTTP ${response.status}).`);

  const body = await response.json() as Record<string, unknown>;
  const accessToken = readString(body.accessToken) ?? readString(body.access_token);
  const user = profileFromBackendUser(body.user);
  if (!accessToken || !user) throw new Error("Identity Service returned an invalid sign-in response.");
  return { accessToken, user };
}

export async function resolveBackendSession(token: string): Promise<UserProfile> {
  if (!token.trim()) throw new Error("Identity Service rejected the access token (HTTP 401).");
  const response = await requestFromIdentity("/me", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) throw new Error(`Identity Service rejected the access token (HTTP ${response.status}).`);
  const user = profileFromBackendUser(await response.json());
  if (!user) throw new Error("Identity Service returned an invalid account profile.");
  return user;
}

export async function revokeBackendToken(token: string): Promise<void> {
  const response = await requestFromIdentity("/revoke", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({})
  });
  if (!response.ok) throw new Error("Identity Service could not revoke the access token.");
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};
