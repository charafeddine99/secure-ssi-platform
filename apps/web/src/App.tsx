import React from "react";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { WalletProvider } from "./context/WalletContext";
import { AppRoutes } from "./routes/AppRoutes";

/**
 * Root Application Component
 * Wraps the SSI Platform with Declarative Routing, Authentication, and Web3 Wallet Providers.
 * Provides specialized modular architectures for:
 * - Public Experience (Landing, Ecosystem Registry, Architecture Docs)
 * - Holder Wallet (Mobile-first tactile credential cards, consent, selective disclosure)
 * - Issuer Console (W3C VC 2.0 issuance wizard, AI threat check, Bitstring revocation)
 * - Verifier Console (OID4VP request builder, 4-step cryptographic verification checklist)
 * - Guardian Network (EIP-4337 M-of-N social recovery quorum visualizer and signing)
 * - Admin Cockpit (Microservice telemetry matrix, smart contracts, audit trail)
 */
export default function App() {
  return (
    <AuthProvider>
      <WalletProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </WalletProvider>
    </AuthProvider>
  );
}
