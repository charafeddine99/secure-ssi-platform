import React, { useEffect, useState, ReactNode } from "react";
import { ethers } from "ethers";
import {
  AuthContext,
  UserProfile,
  DEMO_AUTH_ENABLED,
  DEMO_CREDENTIALS,
  authenticateBackend,
  resolveBackendSession,
  revokeBackendToken
} from "./AuthContext";

const ACCESS_TOKEN_KEYS = ["ssi_access_token", "secure_ssi_token"] as const;

function readAccessToken(): string | null {
  for (const key of ACCESS_TOKEN_KEYS) {
    const value = localStorage.getItem(key);
    if (value) return value;
  }
  return null;
}

function clearLocalSession(): void {
  for (const key of ACCESS_TOKEN_KEYS) localStorage.removeItem(key);
  // Legacy builds stored client-authored roles and wallet material here. The
  // backend token is now the only source used to restore an authenticated user.
  localStorage.removeItem("secure_ssi_user");
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => readAccessToken());
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthLoading, setAuthLoading] = useState<boolean>(() => Boolean(readAccessToken()));
  const [isDemoEvaluationMode, setDemoEvaluationModeState] = useState(DEMO_AUTH_ENABLED);

  useEffect(() => {
    localStorage.removeItem("secure_ssi_user");
  }, []);

  useEffect(() => {
    let active = true;
    if (!token) {
      setUser(null);
      setAuthLoading(false);
      return () => { active = false; };
    }

    setAuthLoading(true);
    resolveBackendSession(token)
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch(() => {
        if (!active) return;
        clearLocalSession();
        setToken(null);
        setUser(null);
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });

    return () => { active = false; };
  }, [token]);

  const login = async (email: string, pass: string): Promise<boolean> => {
    setAuthLoading(true);
    try {
      const session = await authenticateBackend(email, pass);
      if (!session) return false;
      localStorage.setItem("ssi_access_token", session.accessToken);
      localStorage.setItem("secure_ssi_token", session.accessToken);
      setToken(session.accessToken);
      setUser(session.user);
      return true;
    } finally {
      setAuthLoading(false);
    }
  };

  const switchDemoRole = async (role: UserProfile["role"]): Promise<boolean> => {
    if (!DEMO_AUTH_ENABLED) return false;
    const credentials = DEMO_CREDENTIALS[role];
    if (!credentials) return false;
    // Demo accounts still authenticate through the same backend token flow;
    // the browser never assigns a role or treats a failed exchange as a login.
    return login(credentials.username, credentials.pass);
  };

  const loginWithMetaMask = async (): Promise<boolean> => {
    // Address connection is available through WalletProvider. This application
    // has no nonce challenge/signature verification endpoint, so it is not login.
    return false;
  };

  const register = (
    name: string,
    nationalId: string,
    email: string,
    organization: string,
    password?: string
  ): { user: UserProfile; seedPhrase: string } => {
    if (!DEMO_AUTH_ENABLED) {
      throw new Error("Local demo wallet creation is disabled in this build.");
    }
    void password;
    const wallet = ethers.Wallet.createRandom();
    const seedPhrase = wallet.mnemonic?.phrase;
    if (!seedPhrase) throw new Error("The local demo wallet did not produce a recovery phrase.");

    // This creates a browser-side wallet artifact only. It does not create an
    // Identity Service account, DID, or authenticated session.
    return {
      user: {
        name,
        nationalId: nationalId || "NOT_ASSESSED",
        email,
        organization: organization || "Local demo wallet",
        did: "",
        walletAddress: wallet.address,
        assuranceLevel: "UNASSESSED",
        role: "HOLDER",
        permissions: []
      },
      seedPhrase
    };
  };

  const logout = (): void => {
    const activeToken = token;
    clearLocalSession();
    setToken(null);
    setUser(null);
    if (activeToken) void revokeBackendToken(activeToken).catch(() => undefined);
  };

  const quickDemoLogin = (): Promise<boolean> => switchDemoRole("HOLDER");
  const setDemoEvaluationMode = (enabled: boolean): void => {
    setDemoEvaluationModeState(DEMO_AUTH_ENABLED && enabled);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: Boolean(token && user),
        isAuthLoading,
        isDemoEvaluationMode,
        setDemoEvaluationMode,
        switchDemoRole,
        login,
        loginWithMetaMask,
        register,
        logout,
        quickDemoLogin
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
