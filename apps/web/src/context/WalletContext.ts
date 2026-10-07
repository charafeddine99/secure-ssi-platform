import { createContext, useContext } from "react";
import type { BrowserProvider, Contract, JsonRpcSigner } from "ethers";

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

export const WalletContext = createContext<WalletContextType | undefined>(undefined);

export const useWallet = (): WalletContextType => {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error("useWallet must be used within a WalletProvider");
  }
  return context;
};
