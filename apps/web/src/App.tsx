import React, { useState } from "react";
import { WalletProvider, useWallet } from "./context/WalletContext";
import { CredentialVault } from "./components/dashboard/CredentialVault";
import { VerificationModal } from "./components/dashboard/VerificationModal";
import { EmergencyRecoveryCenter } from "./components/dashboard/EmergencyRecoveryCenter";

const DashboardContent: React.FC = () => {
  const { account, chainId, isConnecting, connectWallet, disconnectWallet, error } = useWallet();
  const [isVerificationModalOpen, setIsVerificationModalOpen] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const handleVerificationResult = (success: boolean) => {
    if (success) {
      setToastMessage("Verification Successful: Proof presented to dApp!");
    } else {
      setToastMessage("Verification Declined: Request was rejected.");
    }
    setTimeout(() => setToastMessage(null), 4000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Identity Platform Name */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center font-black text-white text-base shadow-lg shadow-indigo-500/25">
              SI
            </div>
            <div>
              <span className="font-bold text-white text-base tracking-tight">Secure SSI Platform</span>
              <span className="hidden sm:inline-block ml-2 text-[11px] font-semibold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                Layer 4 Dashboard
              </span>
            </div>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-3">
            {/* Simulate dApp Request Button */}
            <button
              onClick={() => setIsVerificationModalOpen(true)}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 active:bg-slate-800 text-slate-200 hover:text-white rounded-xl text-xs font-medium transition border border-slate-700/60 shadow-sm flex items-center gap-1.5"
            >
              <span>🔔</span>
              <span className="hidden md:inline">Simulate dApp Request</span>
            </button>

            {/* Wallet Connect / Disconnect Button */}
            {account ? (
              <div className="flex items-center gap-2">
                <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700/60 text-xs font-mono text-slate-300">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>{account.slice(0, 6)}...{account.slice(-4)}</span>
                </div>
                <button
                  onClick={disconnectWallet}
                  className="px-3 py-1.5 bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 border border-rose-500/20 rounded-xl text-xs font-medium transition"
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <button
                onClick={connectWallet}
                disabled={isConnecting}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-indigo-600/25 flex items-center gap-2"
              >
                <span>🦊</span>
                <span>{isConnecting ? "Connecting..." : "Connect MetaMask"}</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 bg-indigo-600 text-white text-xs font-medium px-4 py-3 rounded-xl shadow-2xl animate-bounce">
          {toastMessage}
        </div>
      )}

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 flex-1 w-full">
        {/* Connection Notice / Error */}
        {error && (
          <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-2xl text-xs text-amber-300 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Hero Identity Overview Card */}
        <div className="relative overflow-hidden bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
                Decentralized Self-Sovereign Identity
              </span>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Self-Sovereign Identity & Guardian Recovery Dashboard
              </h1>
              <p className="text-sm text-slate-400 max-w-2xl leading-relaxed">
                Seamlessly store W3C Verifiable Credentials, authenticate with third-party dApps via zero-knowledge proofs, and safeguard your account with EIP-4337 2-of-3 Multi-Sig Social Recovery.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row md:flex-col gap-2.5 text-xs font-mono">
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl">
                <span className="text-slate-500 block text-[10px] uppercase font-sans">Active DID:</span>
                <span className="text-slate-200 truncate block max-w-xs">
                  {account ? `did:key:z6Mku${account.slice(2, 12)}...` : "did:key:z6MkuDemoIdentity"}
                </span>
              </div>
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl flex items-center justify-between gap-4">
                <span className="text-slate-500 text-[10px] uppercase font-sans">EVM Chain:</span>
                <span className="text-indigo-400 font-bold">{chainId ? `Chain ID ${chainId}` : "Hardhat Node (31337)"}</span>
              </div>
            </div>
          </div>
        </div>

        {/* 1. Component 1: Credential Vault */}
        <section id="credential-vault">
          <CredentialVault />
        </section>

        {/* 2. Component 3: Emergency Recovery Center */}
        <section id="emergency-recovery">
          <EmergencyRecoveryCenter />
        </section>

        {/* 3. Component 2: Verification Request Modal */}
        <VerificationModal
          isOpen={isVerificationModalOpen}
          onClose={() => setIsVerificationModalOpen(false)}
          onVerificationResult={handleVerificationResult}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <p>
          Secure SSI Graduation Project • Sakarya University of Applied Sciences • Charaf Eddine Bessanane
        </p>
        <p className="text-[11px] text-slate-600 mt-1">
          Solidity Hardhat Layer 1 • AI Fraud Detection Layer 2 • SSI W3C VC Layer 3 • React Ethers.js Layer 4
        </p>
      </footer>
    </div>
  );
};

export default function App() {
  return (
    <WalletProvider>
      <DashboardContent />
    </WalletProvider>
  );
}
