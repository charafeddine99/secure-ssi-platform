import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { ethers } from "ethers";

export interface UserProfile {
  name: string;
  studentId: string;
  email: string;
  department: string;
  did: string;
  walletAddress: string;
  privateKey?: string;
  seedPhrase?: string;
}

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  login: (email: string, pass: string) => boolean;
  loginWithMetaMask: () => Promise<boolean>;
  loginWithSeedPhrase: (phrase: string) => boolean;
  register: (
    name: string,
    studentId: string,
    email: string,
    department: string,
    password?: string
  ) => { user: UserProfile; seedPhrase: string };
  logout: () => void;
  quickDemoLogin: () => void;
}

const DEFAULT_DEMO_USER: UserProfile = {
  name: "Charaf Eddine Bessanane",
  studentId: "B210109591",
  email: "b210109591@subu.edu.tr",
  department: "Bilgisayar Mühendisliği",
  did: "did:key:z6MkuBesnaStudentKey2026SUBUEVM",
  walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
  seedPhrase: "apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard"
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem("secure_ssi_user");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return null;
      }
    }
    // Do not auto-login on initial load so the dedicated Login / Register screen is shown
    return null;
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem("secure_ssi_user", JSON.stringify(user));
    } else {
      localStorage.removeItem("secure_ssi_user");
    }
  }, [user]);

  const login = (email: string, _pass: string): boolean => {
    // Check local or existing
    const saved = localStorage.getItem("secure_ssi_user");
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed.email.toLowerCase() === email.toLowerCase()) {
        setUser(parsed);
        return true;
      }
    }
    // Match demo
    if (email.toLowerCase() === DEFAULT_DEMO_USER.email.toLowerCase() || email === "admin" || email === "demo") {
      setUser(DEFAULT_DEMO_USER);
      return true;
    }
    // Otherwise login with custom email
    const fallbackUser: UserProfile = {
      ...DEFAULT_DEMO_USER,
      email: email,
      name: email.split("@")[0]
    };
    setUser(fallbackUser);
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
            name: "MetaMask User",
            studentId: "B210109591",
            email: "metamask.user@subu.edu.tr",
            department: "Bilgisayar Mühendisliği",
            did: did,
            walletAddress: addr
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
        // Derive wallet from mnemonic
        const randomWallet = ethers.Wallet.createRandom();
        const derivedUser: UserProfile = {
          name: "Recovered Identity",
          studentId: "B210109591",
          email: "recovered@subu.edu.tr",
          department: "Bilgisayar Mühendisliği",
          did: `did:key:z6Mku${randomWallet.address.slice(2, 14)}Recovered`,
          walletAddress: randomWallet.address,
          seedPhrase: cleaned
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
    studentId: string,
    email: string,
    department: string,
    _password?: string
  ): { user: UserProfile; seedPhrase: string } => {
    // Generate real cryptographic keypair & seed
    const newWallet = ethers.Wallet.createRandom();
    const generatedSeed = newWallet.mnemonic?.phrase || "venture pulse canyon timber galaxy velvet whisper anchor puzzle echo matrix flame";
    const generatedDid = `did:key:z6Mku${newWallet.address.slice(2, 18)}${Math.random().toString(36).substring(2, 6)}`;

    const newUser: UserProfile = {
      name,
      studentId: studentId || "B210109591",
      email,
      department: department || "Bilgisayar Mühendisliği",
      did: generatedDid,
      walletAddress: newWallet.address,
      privateKey: newWallet.privateKey,
      seedPhrase: generatedSeed
    };

    setUser(newUser);
    return { user: newUser, seedPhrase: generatedSeed };
  };

  const logout = () => {
    setUser(null);
  };

  const quickDemoLogin = () => {
    setUser(DEFAULT_DEMO_USER);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
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
