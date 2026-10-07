import React, { useState, useEffect, ReactNode } from "react";
import { ethers } from "ethers";
import {
  AuthContext,
  UserProfile,
  DEMO_CREDENTIALS,
  DEFAULT_DEMO_USER,
  exchangeBackendToken,
} from "./AuthContext";

interface EthereumWindow {
  ethereum?: ethers.Eip1193Provider;
}

function getEthereum(): ethers.Eip1193Provider | undefined {
  if (typeof window === "undefined") return undefined;
  return (window as unknown as EthereumWindow).ethereum;
}

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
      } catch {
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
      ADMIN: "Platform Infrastructure & Security [DEMO ENVIRONMENT]"
    };

    const roleNames: Record<string, string> = {
      HOLDER: "Demo Holder (Charaf Eddine Bessanane)",
      ISSUER: "European Accredited Issuer Authority",
      VERIFIER: "EU Compliance Trust Verifier",
      GUARDIAN: "Shamir Social Recovery Guardian",
      ADMIN: "Root Trust Registry Operator"
    };

    const roleEmails: Record<string, string> = {
      HOLDER: "holder@example.test",
      ISSUER: "issuer@example.test",
      VERIFIER: "verifier@example.test",
      GUARDIAN: "guardian@example.test",
      ADMIN: "admin@example.test"
    };

    const targetEmail = roleEmails[role];
    const cred = DEMO_CREDENTIALS[role];

    const newUser: UserProfile = {
      name: roleNames[role],
      nationalId: `EUDI-${role}-007`,
      email: targetEmail,
      organization: roleOrgs[role],
      did: roleDids[role],
      walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
      assuranceLevel: "HIGH",
      role: role
    };

    setUser(newUser);

    if (cred) {
      const backendToken = await exchangeBackendToken(cred.username, cred.pass);
      if (backendToken) {
        setToken(backendToken);
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
  }, [token, user?.role]);

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
    const eth = getEthereum();
    if (eth) {
      try {
        const provider = new ethers.BrowserProvider(eth);
        const accounts = (await provider.send("eth_requestAccounts", [])) as string[];
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
      } catch (err: unknown) {
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
    } catch (err: unknown) {
      console.error("Seed login error:", err);
    }
    return false;
  };

  const register = (
    name: string,
    nationalId: string,
    email: string,
    organization: string,
    password?: string
  ): { user: UserProfile; seedPhrase: string } => {
    void password;
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
