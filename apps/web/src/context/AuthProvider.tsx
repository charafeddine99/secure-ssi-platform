import React, { useCallback, useEffect, useMemo, useState } from "react";
import { authenticateBackend, resolveBackendSession, revokeBackendToken } from "../api/session.ts";
import type { IdentityPermission } from "../api/session.ts";
import { SESSION_EXPIRED_EVENT } from "../lib/http.ts";
import { clearSessionMarker, hasSessionMarker, markSession } from "../lib/tokenStore.ts";
import { AuthContext, type AuthContextValue, type LoginResult, type SessionUser } from "./AuthContext.ts";

/**
 * Session state is restored only from the Identity Service (/auth/me) through
 * the gateway's HttpOnly session cookie; roles and permissions always come
 * from the server. JavaScript never sees the access token.
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>(() => (hasSessionMarker() ? "checking" : "anonymous"));
  const [sessionExpired, setSessionExpired] = useState(false);

  const refresh = useCallback(async () => {
    if (!hasSessionMarker()) {
      setUser(null);
      setStatus("anonymous");
      return;
    }
    setStatus("checking");
    try {
      setUser(await resolveBackendSession());
      setStatus("authenticated");
    } catch (error) {
      const rejected = error instanceof Error && error.message.includes("rejected the access token");
      if (rejected) clearSessionMarker();
      setUser(null);
      setStatus(rejected ? "anonymous" : "unavailable");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    const onExpired = () => {
      clearSessionMarker();
      setUser((previous) => {
        if (previous) setSessionExpired(true);
        return null;
      });
      setStatus("anonymous");
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  const login = useCallback(async (username: string, password: string): Promise<LoginResult> => {
    try {
      const session = await authenticateBackend(username, password);
      if (!session) return { ok: false, reason: "invalid_credentials", message: "The username or password is incorrect." };
      markSession();
      setUser(session.user);
      setStatus("authenticated");
      setSessionExpired(false);
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: "unavailable", message: error instanceof Error ? error.message : "Sign-in could not be completed." };
    }
  }, []);

  const logout = useCallback(async () => {
    clearSessionMarker();
    setUser(null);
    setStatus("anonymous");
    setSessionExpired(false);
    // Always ask the gateway: it revokes the token and clears the HttpOnly cookie.
    await revokeBackendToken().catch(() => undefined);
  }, []);

  const hasPermission = useCallback(
    (permission: IdentityPermission) => Boolean(user?.permissions.includes(permission)),
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, sessionExpired, login, logout, refresh, hasPermission }),
    [user, status, sessionExpired, login, logout, refresh, hasPermission],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
