import React, { useState, useEffect, ReactNode } from "react";
import { BrowserProvider, Contract, JsonRpcSigner, Eip1193Provider } from "ethers";
import {
  WalletContext,
  WalletContextType,
  EMERGENCY_RECOVERY_ADDRESS,
  EMERGENCY_RECOVERY_ABI,
} from "./WalletContext";

interface EthereumWindow {
  ethereum?: Eip1193Provider & {
    on?: (event: string, handler: (...args: unknown[]) => void) => void;
    removeListener?: (event: string, handler: (...args: unknown[]) => void) => void;
  };
}

function getEthereum(): EthereumWindow["ethereum"] | undefined {
  if (typeof window === "undefined") return undefined;
  return (window as unknown as EthereumWindow).ethereum;
}

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
      const eth = getEthereum();
      if (eth) {
        try {
          const browserProvider = new BrowserProvider(eth);
          setProvider(browserProvider);

          const accounts = (await browserProvider.send("eth_accounts", [])) as string[];
          if (accounts && accounts.length > 0) {
            const userSigner = await browserProvider.getSigner();
            const network = await browserProvider.getNetwork();
            setAccount(accounts[0]);
            setSigner(userSigner);
            setChainId(Number(network.chainId));
          }
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          console.warn("Auto wallet connection skipped:", msg);
        }
      }
    };

    initWallet();

    const eth = getEthereum();
    // Listen to MetaMask account & chain changes
    if (eth && eth.on) {
      const handleAccountsChanged = (...args: unknown[]) => {
        const accounts = args[0] as string[];
        if (accounts && accounts.length > 0) {
          setAccount(accounts[0]);
        } else {
          setAccount(null);
          setSigner(null);
        }
      };

      const handleChainChanged = () => {
        window.location.reload();
      };

      eth.on("accountsChanged", handleAccountsChanged);
      eth.on("chainChanged", handleChainChanged);

      return () => {
        if (eth.removeListener) {
          eth.removeListener("accountsChanged", handleAccountsChanged);
          eth.removeListener("chainChanged", handleChainChanged);
        }
      };
    }
  }, []);

  const connectWallet = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      const eth = getEthereum();
      if (!eth) {
        setError("No browser wallet provider is available. Connect a wallet to use wallet actions.");
        return;
      }

      const browserProvider = new BrowserProvider(eth);
      setProvider(browserProvider);

      const accounts = (await browserProvider.send("eth_requestAccounts", [])) as string[];
      if (accounts && accounts.length > 0) {
        const userSigner = await browserProvider.getSigner();
        const network = await browserProvider.getNetwork();

        setAccount(accounts[0]);
        setSigner(userSigner);
        setChainId(Number(network.chainId));
      }
    } catch (err: unknown) {
      console.error("Wallet connection error:", err);
      const msg = err instanceof Error ? err.message : "Failed to connect wallet.";
      setError(msg);
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

  const value: WalletContextType = {
    account,
    chainId,
    isConnecting,
    provider,
    signer,
    error,
    connectWallet,
    disconnectWallet,
    getEmergencyRecoveryContract
  };

  return (
    <WalletContext.Provider value={value}>
      {children}
    </WalletContext.Provider>
  );
};
