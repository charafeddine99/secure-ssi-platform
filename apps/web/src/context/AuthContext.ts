import { createContext, useContext } from "react";
import type { AppRole, IdentityPermission, SessionProfile } from "../api/session.ts";

export type { AppRole, IdentityPermission };
export type SessionUser = SessionProfile;
export {
  authenticateBackend,
  DEMO_AUTH_ENABLED,
  DEMO_CREDENTIALS,
  IDENTITY_PERMISSIONS,
  resolveBackendSession,
  revokeBackendToken,
} from "../api/session.ts";

export type LoginResult =
  | { ok: true }
  | { ok: false; reason: "invalid_credentials" | "unavailable"; message: string };

export interface AuthContextValue {
  user: SessionUser | null;
  status: "checking" | "authenticated" | "anonymous" | "unavailable";
  sessionExpired: boolean;
  login: (username: string, password: string) => Promise<LoginResult>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  hasPermission: (permission: IdentityPermission) => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>.");
  return value;
}

export function roleLabel(role: AppRole): string {
  switch (role) {
    case "HOLDER": return "Holder";
    case "ISSUER": return "Issuer";
    case "VERIFIER": return "Verifier";
    case "ADMIN": return "Administrator";
  }
}
