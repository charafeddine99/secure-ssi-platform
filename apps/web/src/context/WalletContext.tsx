import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { ethers, BrowserProvider, Contract, JsonRpcSigner } from "ethers";

// ABI for EmergencyRecovery.sol
export const EMERGENCY_RECOVERY_ABI = [
  "function configureGuardians(address[3] guardians) external",
  "function initiateRecovery(address wallet, address newOwner) external",
  "function approveRecovery(address wallet) external",
  "function executeRecovery(address wallet) external",
  "function cancelRecovery(address wallet) external",
  "function getGuardians(address wallet) external view returns (address[3])",
  "function getWalletOwner(address wallet) external view returns (address)",
  "function isWalletConfigured(address wallet) external view returns (bool)",
  "function isGuardianOf(address wallet, address account) external view returns (bool)",
  "function hasGuardianApproved(address wallet, address guardian) external view returns (bool)",
  "function getRecoveryStatus(address wallet) external view returns (address proposedNewOwner, uint256 approvalCount, bool executed, bool active)",
  "function isWalletQuarantined(address wallet) external view returns (bool)",
  "function quarantineWallet(address wallet, string reason) external",
  "function unquarantineWallet(address wallet) external"
];

export const EMERGENCY_RECOVERY_ADDRESS =
  import.meta.env.VITE_EMERGENCY_RECOVERY_ADDRESS || "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512";

export const DID_REGISTRY_ADDRESS =
  import.meta.env.VITE_DID_REGISTRY_ADDRESS || "0x5FbDB2315678afecb367f032d93F642f64180aa3";

export interface WalletContextType {
  account: string | null;
  chainId: number | null;
  isConnecting: boolean;
  provider: BrowserProvider | null;
  signer: JsonRpcSigner | null;
  error: string | null;
  connectWallet: () => Promise<void>;
  disconnectWallet: () => void;
  getEmergencyRecoveryContract: (withSigner?: boolean) => Contract | null;
}

const WalletContext = createContext<WalletContextType | undefined>(undefined);

export const WalletProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [account, setAccount] = useState<string | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [provider, setProvider] = useState<BrowserProvider | null>(null);
  const [signer, setSigner] = useState<JsonRpcSigner | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initialize provider and account on load if already authorized
  useEffect(() => {
    const initWallet = async () => {
      if (typeof window !== "undefined" && (window as any).ethereum) {
        try {
          const browserProvider = new BrowserProvider((window as any).ethereum);
          setProvider(browserProvider);

          const accounts = await browserProvider.send("eth_accounts", []);
          if (accounts && accounts.length > 0) {
            const userSigner = await browserProvider.getSigner();
            const network = await browserProvider.getNetwork();
            setAccount(accounts[0]);
            setSigner(userSigner);
            setChainId(Number(network.chainId));
          }
        } catch (err: any) {
          console.warn("Auto wallet connection skipped:", err?.message || err);
        }
      }
    };
    initWallet();

    // Listen to MetaMask account & chain changes
    if (typeof window !== "undefined" && (window as any).ethereum) {
      const handleAccountsChanged = (accounts: string[]) => {
        if (accounts.length > 0) {
          setAccount(accounts[0]);
        } else {
          setAccount(null);
          setSigner(null);
        }
      };

      const handleChainChanged = () => {
        window.location.reload();
      };

      (window as any).ethereum.on("accountsChanged", handleAccountsChanged);
      (window as any).ethereum.on("chainChanged", handleChainChanged);

      return () => {
        if ((window as any).ethereum.removeListener) {
          (window as any).ethereum.removeListener("accountsChanged", handleAccountsChanged);
          (window as any).ethereum.removeListener("chainChanged", handleChainChanged);
        }
      };
    }
  }, []);

  const connectWallet = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      if (typeof window === "undefined" || !(window as any).ethereum) {
        // Fallback demo account if MetaMask is absent
        const demoAddress = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266";
        setAccount(demoAddress);
        setChainId(31337);
        setError("MetaMask not detected in browser. Connected in Local Hardhat Demo mode.");
        return;
      }

      const browserProvider = new BrowserProvider((window as any).ethereum);
      setProvider(browserProvider);

      const accounts = await browserProvider.send("eth_requestAccounts", []);
      if (accounts && accounts.length > 0) {
        const userSigner = await browserProvider.getSigner();
        const network = await browserProvider.getNetwork();

        setAccount(accounts[0]);
        setSigner(userSigner);
        setChainId(Number(network.chainId));
      }
    } catch (err: any) {
      console.error("Wallet connection error:", err);
      setError(err?.message || "Failed to connect wallet.");
    } finally {
      setIsConnecting(false);
    }
  };

  const disconnectWallet = () => {
    setAccount(null);
    setSigner(null);
    setChainId(null);
    setError(null);
  };

  const getEmergencyRecoveryContract = (withSigner = true): Contract | null => {
    if (!provider) return null;
    const runner = withSigner && signer ? signer : provider;
    return new Contract(EMERGENCY_RECOVERY_ADDRESS, EMERGENCY_RECOVERY_ABI, runner);
  };

  return (
    <WalletContext.Provider
      value={{
        account,
        chainId,
        isConnecting,
        provider,
        signer,
        error,
        connectWallet,
        disconnectWallet,
        getEmergencyRecoveryContract
      }}
    >
      {children}
    </WalletContext.Provider>
  );
};

export const useWallet = (): WalletContextType => {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error("useWallet must be used within a WalletProvider");
  }
  return context;
};
