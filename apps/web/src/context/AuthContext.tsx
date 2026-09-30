import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { ethers } from "ethers";

export interface UserProfile {
  name: string;
  nationalId: string;
  email: string;
  organization: string;
  did: string;
  walletAddress: string;
  privateKey?: string;
  seedPhrase?: string;
  assuranceLevel: "LOW" | "SUBSTANTIAL" | "HIGH";
  role: "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN";
  // Backward compatibility fields for legacy views if any
  studentId?: string;
  department?: string;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isDemoEvaluationMode: boolean;
  setDemoEvaluationMode: (enabled: boolean) => void;
  switchDemoRole: (role: "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN") => void;
  login: (email: string, pass: string) => boolean;
  loginWithMetaMask: () => Promise<boolean>;
  loginWithSeedPhrase: (phrase: string) => boolean;
  register: (
    name: string,
    nationalId: string,
    email: string,
    organization: string,
    password?: string
  ) => { user: UserProfile; seedPhrase: string };
  logout: () => void;
  quickDemoLogin: () => void;
}

const DEMO_CREDENTIALS: Record<string, { username: string; pass: string }> = {
  ADMIN: { username: "admin@example.test", pass: "Admin-Prototype-2026!" },
  ISSUER: { username: "issuer@example.test", pass: "Issuer-Prototype-2026!" },
  VERIFIER: { username: "verifier@example.test", pass: "Verifier-Prototype-2026!" },
  HOLDER: { username: "holder@example.test", pass: "Holder-Prototype-2026!" },
  GUARDIAN: { username: "admin@example.test", pass: "Admin-Prototype-2026!" }
};

async function exchangeBackendToken(username: string, pass: string): Promise<string | null> {
  const endpoints = [
    "http://localhost:8000/api/v1/identity/auth/token",
    "http://localhost:8001/api/v1/auth/token"
  ];
  for (const url of endpoints) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password: pass })
      });
      if (res.ok) {
        const data = await res.json();
        if (data?.accessToken) {
          localStorage.setItem("ssi_access_token", data.accessToken);
          localStorage.setItem("secure_ssi_token", data.accessToken);
          return data.accessToken;
        }
      }
    } catch {
      // Downstream endpoint unreachable, continue
    }
  }
  return null;
}

const DEFAULT_DEMO_USER: UserProfile = {
  name: "Demo Holder (Charaf Eddine Bessanane)",
  nationalId: "DEMO-HOLD-829104",
  email: "holder@example.test",
  organization: "Demo Academic Wallet [DEMO ENVIRONMENT]",
  did: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
  walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
  seedPhrase: "apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard",
  assuranceLevel: "HIGH",
  role: "HOLDER"
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("ssi_access_token") || localStorage.getItem("secure_ssi_token")
  );
  const [isDemoEvaluationMode, setDemoEvaluationMode] = useState<boolean>(true);
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem("secure_ssi_user");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (!parsed.assuranceLevel) {
          return {
            ...DEFAULT_DEMO_USER,
            name: parsed.name || DEFAULT_DEMO_USER.name,
            email: parsed.email || DEFAULT_DEMO_USER.email,
            did: parsed.did || DEFAULT_DEMO_USER.did,
            walletAddress: parsed.walletAddress || DEFAULT_DEMO_USER.walletAddress
          };
        }
        return parsed;
      } catch (e) {
        return null;
      }
    }
    return DEFAULT_DEMO_USER;
  });

  const switchDemoRole = async (role: "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN") => {
    const roleDids: Record<string, string> = {
      HOLDER: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
      ISSUER: "did:ssi:platform:governance-authority",
      VERIFIER: "did:verifier:platform:compliance-office",
      GUARDIAN: "did:guardian:social-recovery:quorum-member",
      ADMIN: "did:admin:platform:system-operator"
    };

    const roleOrgs: Record<string, string> = {
      HOLDER: "Demo Academic Wallet [DEMO ENVIRONMENT]",
      ISSUER: "Demo University (Accredited Issuer) [DEMO ENVIRONMENT]",
      VERIFIER: "Demo Company (Trust Verification) [DEMO ENVIRONMENT]",
      GUARDIAN: "Demo Social Recovery Network [DEMO ENVIRONMENT]",
      ADMIN: "Demo Platform Operations [DEMO ENVIRONMENT]"
    };

    const roleNames: Record<string, string> = {
      HOLDER: "Demo Holder (Charaf Eddine Bessanane)",
      ISSUER: "Demo University Authority",
      VERIFIER: "Demo Company Compliance",
      GUARDIAN: "Demo Quorum Guardian #1",
      ADMIN: "Demo System Administrator"
    };

    const roleEmails: Record<string, string> = {
      HOLDER: "holder@example.test",
      ISSUER: "issuer@example.test",
      VERIFIER: "verifier@example.test",
      GUARDIAN: "admin@example.test",
      ADMIN: "admin@example.test"
    };

    setUser((prev) => {
      const base = prev || DEFAULT_DEMO_USER;
      return {
        ...base,
        role: role,
        name: roleNames[role] || base.name,
        email: roleEmails[role] || base.email,
        did: roleDids[role] || base.did,
        organization: roleOrgs[role] || base.organization
      };
    });

    const cred = DEMO_CREDENTIALS[role];
    if (cred) {
      const liveToken = await exchangeBackendToken(cred.username, cred.pass);
      if (liveToken) {
        setToken(liveToken);
      }
    }
  };

  useEffect(() => {
    if (user) {
      localStorage.setItem("secure_ssi_user", JSON.stringify(user));
    } else {
      localStorage.removeItem("secure_ssi_user");
    }
  }, [user]);

  // Initial attempt to bind live access token on mount
  useEffect(() => {
    if (!token && user?.role) {
      const cred = DEMO_CREDENTIALS[user.role];
      if (cred) {
        exchangeBackendToken(cred.username, cred.pass).then((t) => {
          if (t) setToken(t);
        });
      }
    }
  }, []);

  const login = (email: string, pass: string): boolean => {
    const saved = localStorage.getItem("secure_ssi_user");
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed.email.toLowerCase() === email.toLowerCase()) {
        setUser(parsed);
        return true;
      }
    }
    if (email.toLowerCase() === DEFAULT_DEMO_USER.email.toLowerCase() || email === "admin" || email === "demo") {
      setUser(DEFAULT_DEMO_USER);
      exchangeBackendToken("holder@example.test", "Holder-Prototype-2026!").then((t) => {
        if (t) setToken(t);
      });
      return true;
    }

    const fallbackUser: UserProfile = {
      ...DEFAULT_DEMO_USER,
      email: email,
      name: email.split("@")[0]
    };
    setUser(fallbackUser);

    if (pass) {
      exchangeBackendToken(email, pass).then((t) => {
        if (t) setToken(t);
      });
    }
    return true;
  };

  const loginWithMetaMask = async (): Promise<boolean> => {
    if (typeof window !== "undefined" && (window as any).ethereum) {
      try {
        const provider = new ethers.BrowserProvider((window as any).ethereum);
        const accounts = await provider.send("eth_requestAccounts", []);
        if (accounts && accounts.length > 0) {
          const addr = accounts[0];
          const did = `did:key:z6Mku${addr.slice(2, 14)}MetaMask`;
          const metaMaskUser: UserProfile = {
            name: "Verified Sovereign Identity",
            nationalId: `EVM-${addr.slice(2, 10).toUpperCase()}`,
            email: `holder.${addr.slice(2, 8)}@ssi-vault.io`,
            organization: "Self-Sovereign Identity Network",
            did: did,
            walletAddress: addr,
            assuranceLevel: "HIGH",
            role: "HOLDER"
          };
          setUser(metaMaskUser);
          return true;
        }
      } catch (err) {
        console.error("MetaMask login error:", err);
      }
    }
    return false;
  };

  const loginWithSeedPhrase = (phrase: string): boolean => {
    try {
      const cleaned = phrase.trim();
      const words = cleaned.split(/\s+/);
      if (words.length >= 12) {
        const randomWallet = ethers.Wallet.createRandom();
        const derivedUser: UserProfile = {
          name: "Recovered Sovereign Identity",
          nationalId: `REC-${randomWallet.address.slice(2, 10).toUpperCase()}`,
          email: "recovered.identity@eudi-id.eu",
          organization: "European Digital Identity Framework",
          did: `did:key:z6Mku${randomWallet.address.slice(2, 14)}Recovered`,
          walletAddress: randomWallet.address,
          seedPhrase: cleaned,
          assuranceLevel: "HIGH",
          role: "HOLDER"
        };
        setUser(derivedUser);
        return true;
      }
    } catch (err) {
      console.error("Seed login error:", err);
    }
    return false;
  };

  const register = (
    name: string,
    nationalId: string,
    email: string,
    organization: string,
    _password?: string
  ): { user: UserProfile; seedPhrase: string } => {
    const newWallet = ethers.Wallet.createRandom();
    const generatedSeed = newWallet.mnemonic?.phrase || "venture pulse canyon timber galaxy velvet whisper anchor puzzle echo matrix flame";
    const generatedDid = `did:key:z6Mku${newWallet.address.slice(2, 18)}${Math.random().toString(36).substring(2, 6)}`;

    const newUser: UserProfile = {
      name,
      nationalId: nationalId || "EUDI-ID-902814",
      email,
      organization: organization || "Self-Sovereign Identity Network",
      did: generatedDid,
      walletAddress: newWallet.address,
      privateKey: newWallet.privateKey,
      seedPhrase: generatedSeed,
      assuranceLevel: "HIGH",
      role: "HOLDER"
    };

    setUser(newUser);
    return { user: newUser, seedPhrase: generatedSeed };
  };

  const logout = () => {
    localStorage.removeItem("ssi_access_token");
    localStorage.removeItem("secure_ssi_token");
    localStorage.removeItem("secure_ssi_user");
    setToken(null);
    setUser(null);
  };

  const quickDemoLogin = () => {
    setUser(DEFAULT_DEMO_USER);
    exchangeBackendToken("holder@example.test", "Holder-Prototype-2026!").then((t) => {
      if (t) setToken(t);
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isDemoEvaluationMode,
        setDemoEvaluationMode,
        switchDemoRole,
        login,
        loginWithMetaMask,
        loginWithSeedPhrase,
        register,
        logout,
        quickDemoLogin
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
