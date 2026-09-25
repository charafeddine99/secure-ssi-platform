import React, { useState, useEffect } from "react";
import { useWallet, EMERGENCY_RECOVERY_ADDRESS } from "../../context/WalletContext";
import { ethers } from "ethers";

export const EmergencyRecoveryCenter: React.FC = () => {
  const { account, getEmergencyRecoveryContract } = useWallet();

  // 1. Configure Guardians State (3 distinct addresses)
  const [guardian1, setGuardian1] = useState<string>("0x70997970C51812dc3A010C7d01b50e0d17dc79C8");
  const [guardian2, setGuardian2] = useState<string>("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC");
  const [guardian3, setGuardian3] = useState<string>("0x90F79bf6EB2c4f870365E785982E1f101E93b906");
  const [isConfiguring, setIsConfiguring] = useState<boolean>(false);

  // 2. Lost Device / Initiate Recovery State
  const [lostWalletToRecover, setLostWalletToRecover] = useState<string>("");
  const [proposedNewOwner, setProposedNewOwner] = useState<string>("");
  const [isInitiating, setIsInitiating] = useState<boolean>(false);

  // 3. Guardian Approve Recovery State
  const [compromisedWalletInput, setCompromisedWalletInput] = useState<string>("");
  const [isApproving, setIsApproving] = useState<boolean>(false);

  // On-Chain Status Info
  const [isConfigured, setIsConfigured] = useState<boolean>(false);
  const [configuredGuardians, setConfiguredGuardians] = useState<string[]>([]);
  const [isQuarantined, setIsQuarantined] = useState<boolean>(false);
  const [recoveryStatus, setRecoveryStatus] = useState<{
    proposedOwner: string;
    approvalCount: number;
    executed: boolean;
    active: boolean;
  } | null>(null);

  // Notifications
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Fetch status on account change
  const refreshOnChainStatus = async () => {
    if (!account) return;
    try {
      const contract = getEmergencyRecoveryContract(false);
      if (!contract) return;

      const configured = await contract.isWalletConfigured(account).catch(() => false);
      setIsConfigured(configured);

      if (configured) {
        const guardiansList = await contract.getGuardians(account).catch(() => []);
        setConfiguredGuardians(Array.from(guardiansList));
      }

      const quarantined = await contract.isWalletQuarantined(account).catch(() => false);
      setIsQuarantined(quarantined);

      const statusTuple = await contract.getRecoveryStatus(account).catch(() => null);
      if (statusTuple && (statusTuple[3] || statusTuple[2])) {
        setRecoveryStatus({
          proposedOwner: statusTuple[0],
          approvalCount: Number(statusTuple[1]),
          executed: statusTuple[2],
          active: statusTuple[3]
        });
      } else {
        setRecoveryStatus(null);
      }
    } catch (err) {
      console.warn("Could not query contract status:", err);
    }
  };

  useEffect(() => {
    refreshOnChainStatus();
  }, [account]);

  // Form 1: Configure 3 Guardians
  const handleConfigureGuardians = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);

    if (!account) {
      setActionError("Please connect your wallet first.");
      return;
    }

    if (!ethers.isAddress(guardian1) || !ethers.isAddress(guardian2) || !ethers.isAddress(guardian3)) {
      setActionError("All 3 guardian addresses must be valid Ethereum addresses.");
      return;
    }

    if (guardian1 === guardian2 || guardian1 === guardian3 || guardian2 === guardian3) {
      setActionError("All 3 guardian addresses must be distinct.");
      return;
    }

    setIsConfiguring(true);
    try {
      const contract = getEmergencyRecoveryContract(true);
      if (!contract) throw new Error("Contract runner not available.");

      const tx = await contract.configureGuardians([guardian1, guardian2, guardian3]);
      setActionSuccess(`Transaction submitted: ${tx.hash}. Waiting for confirmation...`);
      await tx.wait();

      setActionSuccess("3 Guardians successfully configured on-chain!");
      await refreshOnChainStatus();
    } catch (err: any) {
      console.error("Configure guardians failed:", err);
      setActionError(err?.reason || err?.message || "Failed to configure guardians.");
    } finally {
      setIsConfiguring(false);
    }
  };

  // Form 2: Initiate Recovery (for lost device scenario)
  const handleInitiateRecovery = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);

    const targetWallet = lostWalletToRecover || account;
    if (!targetWallet || !ethers.isAddress(targetWallet)) {
      setActionError("Please specify a valid compromised wallet address to recover.");
      return;
    }

    if (!proposedNewOwner || !ethers.isAddress(proposedNewOwner)) {
      setActionError("Please specify a valid proposed replacement address.");
      return;
    }

    setIsInitiating(true);
    try {
      const contract = getEmergencyRecoveryContract(true);
      if (!contract) throw new Error("Contract runner not available.");

      const tx = await contract.initiateRecovery(targetWallet, proposedNewOwner);
      setActionSuccess(`Initiate Recovery TX submitted: ${tx.hash}`);
      await tx.wait();

      setActionSuccess("Recovery initiated! 1 of 3 guardian approvals recorded.");
      await refreshOnChainStatus();
    } catch (err: any) {
      console.error("Initiate recovery failed:", err);
      setActionError(err?.reason || err?.message || "Failed to initiate recovery. Are you an authorized guardian?");
    } finally {
      setIsInitiating(false);
    }
  };

  // Form 3: Guardian Approves Recovery (triggers 2-of-3 threshold)
  const handleApproveRecovery = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);

    if (!compromisedWalletInput || !ethers.isAddress(compromisedWalletInput)) {
      setActionError("Please input the valid address of the compromised wallet undergoing recovery.");
      return;
    }

    setIsApproving(true);
    try {
      const contract = getEmergencyRecoveryContract(true);
      if (!contract) throw new Error("Contract runner not available.");

      const tx = await contract.approveRecovery(compromisedWalletInput);
      setActionSuccess(`Approve Recovery TX submitted: ${tx.hash}`);
      const receipt = await tx.wait();

      setActionSuccess(`Guardian approval recorded! (Block: ${receipt.blockNumber}). If 2-of-3 threshold is reached, ownership transfers automatically.`);
      await refreshOnChainStatus();
    } catch (err: any) {
      console.error("Approve recovery failed:", err);
      setActionError(err?.reason || err?.message || "Failed to approve recovery. Verify that you are an authorized guardian.");
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-rose-500/10 text-rose-400 rounded-lg text-lg">🆘</span>
            <h2 className="text-xl font-bold text-white tracking-tight">Emergency Recovery Center</h2>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            EIP-4337 Inspired 2-out-of-3 Multi-Sig Guardian Social Recovery on Blockchain.
          </p>
        </div>

        <div className="text-xs font-mono text-slate-400 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 truncate max-w-xs" title={EMERGENCY_RECOVERY_ADDRESS}>
          Contract: <span className="text-indigo-400">{EMERGENCY_RECOVERY_ADDRESS.slice(0, 8)}...{EMERGENCY_RECOVERY_ADDRESS.slice(-6)}</span>
        </div>
      </div>

      {/* Global Alerts */}
      {actionSuccess && (
        <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-400 flex items-center justify-between">
          <span>{actionSuccess}</span>
          <button onClick={() => setActionSuccess(null)} className="font-bold ml-2">✕</button>
        </div>
      )}

      {actionError && (
        <div className="p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400 flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="font-bold ml-2">✕</button>
        </div>
      )}

      {/* Account Security Status Banner */}
      <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Guardian Setup:</span>
          {isConfigured ? (
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
              3 Guardians Configured ✓
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
              Not Configured
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400">Account Safety:</span>
          {isQuarantined ? (
            <span className="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/40 font-bold animate-pulse">
              QUARANTINED BY AI (LOCKED)
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
              Operational & Secure
            </span>
          )}
        </div>

        {recoveryStatus && recoveryStatus.active && (
          <div className="flex items-center gap-2">
            <span className="text-amber-400 font-semibold">Active Multi-Sig:</span>
            <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-mono font-bold">
              {recoveryStatus.approvalCount} / 3 Approvals (Target: 2)
            </span>
          </div>
        )}
      </div>

      {/* Main 3 Sections Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Section 1: Configure 3 Guardians */}
        <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-xs">1</span>
              <h3 className="font-semibold text-white text-sm">Configure 3 Guardians</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Initialize 3 trusted contact addresses. In emergency situations, 2 of 3 must approve to recover account.
            </p>

            <form onSubmit={handleConfigureGuardians} className="space-y-3">
              <div>
                <label className="text-[11px] font-medium text-slate-400 block mb-1">Guardian 1 Address</label>
                <input
                  type="text"
                  value={guardian1}
                  onChange={(e) => setGuardian1(e.target.value)}
                  placeholder="0x..."
                  className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none transition"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-slate-400 block mb-1">Guardian 2 Address</label>
                <input
                  type="text"
                  value={guardian2}
                  onChange={(e) => setGuardian2(e.target.value)}
                  placeholder="0x..."
                  className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none transition"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-slate-400 block mb-1">Guardian 3 Address</label>
                <input
                  type="text"
                  value={guardian3}
                  onChange={(e) => setGuardian3(e.target.value)}
                  placeholder="0x..."
                  className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none transition"
                />
              </div>

              <button
                type="submit"
                disabled={isConfiguring}
                className="w-full mt-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white font-medium text-xs rounded-xl transition duration-150 shadow-md shadow-indigo-600/20"
              >
                {isConfiguring ? "Registering on Blockchain..." : "Configure Guardians"}
              </button>
            </form>
          </div>
        </div>

        {/* Section 2: Initiate Recovery (Lost Device Scenario) */}
        <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold text-xs">2</span>
              <h3 className="font-semibold text-white text-sm">Lost Device Recovery</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Lost your device or private key? A registered Guardian triggers account migration to your new key.
            </p>

            <form onSubmit={handleInitiateRecovery} className="space-y-3">
              <div>
                <label className="text-[11px] font-medium text-slate-400 block mb-1">Lost / Compromised Wallet</label>
                <input
                  type="text"
                  value={lostWalletToRecover}
                  onChange={(e) => setLostWalletToRecover(e.target.value)}
                  placeholder={account || "0x..."}
                  className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none transition"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-slate-400 block mb-1">Proposed Replacement Address</label>
                <input
                  type="text"
                  value={proposedNewOwner}
                  onChange={(e) => setProposedNewOwner(e.target.value)}
                  placeholder="0x... (New Device Wallet)"
                  className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none transition"
                />
              </div>

              <button
                type="submit"
                disabled={isInitiating}
                className="w-full mt-2 py-2.5 px-4 bg-rose-600 hover:bg-rose-500 active:bg-rose-700 disabled:opacity-50 text-white font-semibold text-xs rounded-xl transition duration-150 shadow-lg shadow-rose-600/30 flex items-center justify-center gap-1.5"
              >
                <span>⚠️</span>
                <span>{isInitiating ? "Initiating on Chain..." : "Initiate Recovery"}</span>
              </button>
            </form>
          </div>
        </div>

        {/* Section 3: Guardian Approves Recovery (2-of-3 Multi-Sig Threshold) */}
        <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">3</span>
              <h3 className="font-semibold text-white text-sm">Guardian Multi-Sig Approval</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Authorized Guardians input the target wallet to cast their multi-sig vote. Automatically executes upon 2nd approval.
            </p>

            <form onSubmit={handleApproveRecovery} className="space-y-3">
              <div>
                <label className="text-[11px] font-medium text-slate-400 block mb-1">Target Compromised Wallet</label>
                <input
                  type="text"
                  value={compromisedWalletInput}
                  onChange={(e) => setCompromisedWalletInput(e.target.value)}
                  placeholder="0x... (Wallet undergoing recovery)"
                  className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-white font-mono outline-none transition"
                />
              </div>

              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 text-[11px] text-slate-400 space-y-1">
                <span className="font-medium text-slate-300 block">Multi-Sig Consensus Rules:</span>
                <p>• Requires 2 out of 3 registered guardians.</p>
                <p>• 2nd approval immediately transfers ownership on-chain.</p>
              </div>

              <button
                type="submit"
                disabled={isApproving}
                className="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white font-semibold text-xs rounded-xl transition duration-150 shadow-md shadow-emerald-600/20"
              >
                {isApproving ? "Casting Guardian Approval..." : "Approve Recovery (2/3)"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
