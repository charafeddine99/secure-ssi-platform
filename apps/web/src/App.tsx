import React from "react";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthProvider";
import { WalletProvider } from "./context/WalletProvider";
import { AppRoutes } from "./routes/AppRoutes";

/**
 * Root Application Component
 * Wraps the SSI Platform with Declarative Routing, Authentication, and Web3 Wallet Providers.
 * Provides specialized modular architectures for:
 * - Public Experience (Landing, Ecosystem Registry, Architecture Docs)
 * - Holder Wallet (prototype credential display and consent flows; selective disclosure is not implemented)
 * - Issuer Console (OID4VCI and credential-status prototype workflows)
 * - Verifier Console (OID4VP request builder and backend policy-result view)
 * - Guardian recovery workflow prototype (independent DID signatures and EIP-4337 account abstraction are not implied)
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
