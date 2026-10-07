import { createContext, useContext } from "react";

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
  studentId?: string;
  department?: string;
}

export interface AuthContextType {
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

export const DEMO_CREDENTIALS: Record<string, { username: string; pass: string }> = {
  ADMIN: { username: "admin@example.test", pass: "Admin-Prototype-2026!" },
  ISSUER: { username: "issuer@example.test", pass: "Issuer-Prototype-2026!" },
  VERIFIER: { username: "verifier@example.test", pass: "Verifier-Prototype-2026!" },
  HOLDER: { username: "holder@example.test", pass: "Holder-Prototype-2026!" },
  GUARDIAN: { username: "admin@example.test", pass: "Admin-Prototype-2026!" }
};

export async function exchangeBackendToken(username: string, pass: string): Promise<string | null> {
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

export const DEFAULT_DEMO_USER: UserProfile = {
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

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
