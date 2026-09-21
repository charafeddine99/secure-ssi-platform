import React from "react";
import { AuthProvider } from "./context/AuthContext";
import { WalletProvider } from "./context/WalletContext";
import { MasterPlatform } from "./pages/MasterPlatform";

/**
 * Root Application Component
 * Wraps the Master Platform with Authentication and Web3 Wallet Providers.
 * Supports:
 * - Login & Registration (W3C DID derivation, 12-word seed phrase, EVM address)
 * - Holder Credential Vault (W3C JSON-LD, Ed25519 signature proof, QR presentation)
 * - Issuer (SUBÜ Graduation Degree issuance anchored with AI Risk check & Hardhat)
 * - Verifier (Zero-Knowledge Proof selective disclosure & Revocation check)
 * - AI Fraud Detection (Real-time XGBoost + Autoencoder scoring, quarantine smart contract)
 * - Emergency Recovery (EIP-4337 2-of-3 / 3-of-5 Guardian social recovery)
 * - Blockchain Registry Explorer (DIDRegistry.sol & EmergencyRecovery.sol)
 */
export default function App() {
  return (
    <AuthProvider>
      <WalletProvider>
        <MasterPlatform />
      </WalletProvider>
    </AuthProvider>
  );
}
