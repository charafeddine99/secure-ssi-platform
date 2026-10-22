import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { StatusChip } from "../../components/common/StatusChip";
import {
  fetchRecoveryPolicy,
  fetchGuardians,
  fetchRecoveryRequests,
  getOrCreateHolderWallet,
  canInitiateRecovery,
  initiateRecoveryRequest,
  cancelRecoveryRequest,
  RecoveryPolicy,
  RecoveryRequest,
  BackendGuardian
} from "../../services/api";
import {
  KeyRound,
  Users,
  Check,
  AlertTriangle,
  ShieldAlert,
  XCircle,
} from "lucide-react";

export const SecuritySettingsPage: React.FC = () => {
  const { user } = useAuth();

  // Recovery State
  const [policy, setPolicy] = useState<RecoveryPolicy | null>(null);
  const [guardiansList, setGuardiansList] = useState<BackendGuardian[]>([]);
  const [activePetition, setActivePetition] = useState<RecoveryRequest | null>(null);
  const [loadingRecovery, setLoadingRecovery] = useState(true);
  const [holderWalletId, setHolderWalletId] = useState<string | null>(null);
  const [showRecoveryModal, setShowRecoveryModal] = useState(false);
  const [recoveryReason, setRecoveryReason] = useState("ACCOUNT_COMPROMISE");
  const [customReason, setCustomReason] = useState("");
  const [submittingRecovery, setSubmittingRecovery] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const activeGuardianCount = guardiansList.filter((guardian) => guardian.approved === 1).length;
  const recoveryCanStart = canInitiateRecovery(
    holderWalletId,
    policy,
    activeGuardianCount,
    activePetition !== null,
  );

  const loadRecoveryData = async () => {
    setLoadingRecovery(true);
    try {
      const wallet = await getOrCreateHolderWallet();
      setHolderWalletId(wallet.walletId);
      const [pol, guards, reqs] = await Promise.all([
        fetchRecoveryPolicy(wallet.walletId),
        fetchGuardians(wallet.walletId),
        fetchRecoveryRequests(10)
      ]);
      setPolicy(pol);
      setGuardiansList(guards);

      const active = reqs.find(
        (r) => r.walletId === wallet.walletId
          && ["PENDING_APPROVALS", "QUORUM_REACHED", "WAITING_TIMELOCK", "READY_FOR_EXECUTION"].includes(r.status)
      );
      setActivePetition(active || null);
    } catch (err: unknown) {
      console.warn("Could not load recovery configuration:", err);
      setHolderWalletId(null);
      setPolicy(null);
      setGuardiansList([]);
      setActivePetition(null);
      setStatusMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Recovery Service state is unavailable."
      });
    } finally {
      setLoadingRecovery(false);
    }
  };

  useEffect(() => {
    loadRecoveryData();
  }, []);

  const handleInitiateRecovery = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingRecovery(true);
    setStatusMsg(null);
    try {
      if (!holderWalletId) throw new Error("A server-managed holder wallet is required before recovery can be requested.");
      if (!policy || policy.walletId !== holderWalletId) throw new Error("The Recovery Service policy for this wallet is unavailable.");
      if (activePetition) throw new Error("An active recovery request already exists.");
      if (!recoveryCanStart) throw new Error("Active Guardian records cannot satisfy this wallet's Recovery Service policy.");
      const reasonText = customReason.trim() || recoveryReason;
      const res = await initiateRecoveryRequest({
        walletId: holderWalletId,
        reason: reasonText
      });
      setStatusMsg({
        type: "success",
        text: `Recovery Service request ${res.requestId} created. Guardian notification delivery is not confirmed.`
      });
      setShowRecoveryModal(false);
      await loadRecoveryData();
    } catch (err: unknown) {
      setStatusMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to initiate recovery petition."
      });
    } finally {
      setSubmittingRecovery(false);
    }
  };

  const handleCancelRecovery = async () => {
    if (!activePetition) return;
    setStatusMsg(null);
    try {
      await cancelRecoveryRequest(activePetition.requestId);
      setStatusMsg({
        type: "success",
        text: `Recovery petition ${activePetition.requestId} cancelled.`
      });
      await loadRecoveryData();
    } catch (err: unknown) {
      setStatusMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to cancel recovery petition."
      });
    }
  };

  return (
    <main className="holder-page holder-security-page" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <header className="holder-page-header">
        <div>
          <p className="holder-page-eyebrow">PERSONAL WALLET</p>
          <h1>Security and recovery</h1>
          <p>Review wallet identity and the Recovery Service policy for this account.</p>
        </div>
      </header>
      {loadingRecovery && <p className="holder-inline-status" role="status">Loading wallet security settings…</p>}
      {/* Sovereign Identity Overview */}
      <div
        className="holder-security-card holder-security-identity"
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <KeyRound size={20} color="#60a5fa" />
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
              Wallet identity
            </h2>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.8rem" }}>
          <div style={{ backgroundColor: "#0d131f", padding: "10px 12px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ color: "#94a3b8" }}>Decentralized Identifier (DID):</span>
            <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px", wordBreak: "break-all" }}>
              {user?.did || "Not provided by Identity Service"}
            </div>
          </div>

          <div style={{ backgroundColor: "#0d131f", padding: "10px 12px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ color: "#94a3b8" }}>EVM Wallet Address:</span>
            <div style={{ fontFamily: "var(--font-mono)", color: "#c084fc", marginTop: "2px" }}>
              {user?.walletAddress || "No linked EVM address"}
            </div>
          </div>
        </div>
      </div>

      {statusMsg && (
        <div
          className={`holder-notice holder-notice--${statusMsg.type}`}
          role={statusMsg.type === "error" ? "alert" : "status"}
          style={{
            padding: "12px 16px",
            borderRadius: "8px",
            backgroundColor: statusMsg.type === "success" ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
            border: `1px solid ${statusMsg.type === "success" ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
            color: statusMsg.type === "success" ? "#34d399" : "#f87171",
            fontSize: "0.85rem",
            display: "flex",
            alignItems: "center",
            gap: "8px"
          }}
        >
          {statusMsg.type === "success" ? <Check size={16} /> : <AlertTriangle size={16} />}
          {statusMsg.text}
        </div>
      )}

      {/* Active Recovery Petition Warning Banner */}
      {activePetition && (
        <div
          className="holder-active-recovery"
          style={{
            backgroundColor: "#1c1917",
            borderRadius: "14px",
            border: "1px solid #d97706",
            padding: "18px 20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "14px"
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
            <AlertTriangle size={22} color="#f59e0b" style={{ flexShrink: 0, marginTop: "2px" }} />
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontWeight: 700, color: "#ffffff", fontSize: "0.95rem" }}>
                  Active Recovery Petition: {activePetition.requestId}
                </span>
                <StatusChip status={activePetition.status} size="sm" />
              </div>
              <p style={{ margin: "4px 0 0 0", fontSize: "0.8rem", color: "#cbd5e1" }}>
                Approvals: <strong>{activePetition.approvalsCount} of {activePetition.requiredCount}</strong>
                {activePetition.timelockExpiresAt && (
                  <span style={{ color: "#fbbf24", marginLeft: "8px" }}>
                    • Time-lock active until {new Date(activePetition.timelockExpiresAt).toLocaleTimeString()}
                  </span>
                )}
              </p>
            </div>
          </div>

          <button
            type="button"
            className="holder-danger-action"
            onClick={handleCancelRecovery}
            style={{
              padding: "8px 14px",
              borderRadius: "8px",
              backgroundColor: "rgba(239, 68, 68, 0.2)",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              color: "#f87171",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            <XCircle size={14} />
            Cancel Recovery
          </button>
        </div>
      )}

      {/* Wallet key export and mnemonic recovery are not implemented. */}
      <div
        className="holder-security-card holder-security-key-state"
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", margin: "0 0 8px 0" }}>
          Key export and recovery phrase restore are unavailable
        </h3>
        <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: 0 }}>
          Wallet keys are server-managed. This account has no local recovery phrase to export or restore.
        </p>
      </div>

      {/* Guardian records from the Recovery Service; independent signatures are not implied. */}
      <div
        className="holder-security-card holder-security-recovery"
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Users size={18} color="#fbbf24" />
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
              Guardian records and recovery policy
            </h3>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "0.7rem", color: "#34d399", fontWeight: 600 }}>
              Threshold: {policy ? `${policy.minimumApprovals}-of-${policy.maximumGuardians}` : "Unavailable"}
            </span>

            {!activePetition && (
              <button
                type="button"
                onClick={() => setShowRecoveryModal(true)}
                disabled={!recoveryCanStart}
                title={recoveryCanStart ? "Create a Recovery Service request" : "A valid backend policy and enough active Guardian records are required."}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  backgroundColor: "#dc2626",
                  color: "#ffffff",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  border: "none",
                  cursor: recoveryCanStart ? "pointer" : "not-allowed",
                  opacity: recoveryCanStart ? 1 : 0.55,
                  display: "flex",
                  alignItems: "center",
                  gap: "4px"
                }}
              >
                <ShieldAlert size={13} />
                Initiate Emergency Recovery
              </button>
            )}
          </div>

        {!activePetition && !recoveryCanStart && (
          <p role="status" style={{ fontSize: "0.75rem", color: "#fbbf24", margin: "0 0 12px" }}>
            Recovery requests are unavailable until this wallet has a valid backend policy and enough active Guardian records.
          </p>
        )}
        </div>

        {/* Policy Specs Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "10px",
            marginBottom: "16px",
            fontSize: "0.75rem",
            backgroundColor: "#0d131f",
            padding: "12px",
            borderRadius: "8px",
            border: "1px solid #1f2937"
          }}
        >
          <div>
            <span style={{ color: "#94a3b8" }}>Quorum Threshold:</span>
            <div style={{ color: "#60a5fa", fontWeight: 600, marginTop: "2px" }}>
              {policy ? `${policy.minimumApprovals} of ${policy.maximumGuardians} approvals` : "Policy unavailable"}
            </div>
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Time-Lock Delay:</span>
            <div style={{ color: "#fbbf24", fontWeight: 600, marginTop: "2px" }}>
              {policy ? `${policy.timeLockSeconds} seconds` : "Unavailable"}
            </div>
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Approval Window:</span>
            <div style={{ color: "#34d399", fontWeight: 600, marginTop: "2px" }}>
              {policy ? `${Math.round(policy.approvalWindowSeconds / 60)} minutes` : "Unavailable"}
            </div>
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Anti-Compromise:</span>
            <div style={{ color: "#c084fc", fontWeight: 600, marginTop: "2px" }}>
              Status unavailable; key rotation is not confirmed
            </div>
          </div>
        </div>

        {/* Guardians List */}
        <div className="holder-guardian-list" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {!loadingRecovery && guardiansList.length === 0 && (
            <p className="holder-empty-inline">No Guardian records were returned for this wallet.</p>
          )}
          {guardiansList.map((g, i) => (
            <div
              key={i}
              className="holder-guardian-row"
              style={{
                backgroundColor: "#0d131f",
                padding: "10px 14px",
                borderRadius: "8px",
                border: "1px solid #1f2937",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "8px"
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#f8fafc" }}>
                    {g.guardian_name}
                  </span>
                  <span style={{ fontSize: "0.7rem", color: "#60a5fa" }}>({g.guardian_role})</span>
                </div>
                <div style={{ fontSize: "0.7rem", fontFamily: "var(--font-mono)", color: "#94a3b8", marginTop: "2px" }}>
                  {g.guardian_address}
                </div>
              </div>
              <span
                className={g.approved ? "holder-record-status is-active" : "holder-record-status"}
                style={{
                  fontSize: "0.68rem",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  backgroundColor: "rgba(16, 185, 129, 0.15)",
                  color: "#34d399",
                  fontWeight: 600
                }}
              >
                {g.approved ? "ACTIVE SERVICE RECORD" : "SERVICE RECORD NOT ACTIVE"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Emergency Recovery Initiation Modal */}
      {showRecoveryModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px"
          }}
        >
          <div
            className="holder-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="holder-recovery-dialog-title"
            style={{
              backgroundColor: "#111827",
              borderRadius: "16px",
              border: "1px solid #dc2626",
              padding: "24px",
              maxWidth: "500px",
              width: "100%",
              display: "flex",
              flexDirection: "column",
              gap: "16px"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <ShieldAlert size={24} color="#ef4444" />
              <h3 id="holder-recovery-dialog-title" style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                Create Recovery Service request
              </h3>
            </div>

            <p style={{ fontSize: "0.85rem", color: "#cbd5e1", margin: 0, lineHeight: 1.5 }}>
              This creates a Recovery Service request only. It does not prove independent Guardian DID signatures, split or recover key shares, rotate keys, change credential status, notify guardians, or submit an on-chain transaction. The active service policy is shown only when the backend returns it.
            </p>

            <form onSubmit={handleInitiateRecovery} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ fontSize: "0.8rem", color: "#94a3b8", display: "block", marginBottom: "6px" }}>
                  Incident Classification:
                </label>
                <select
                  value={recoveryReason}
                  onChange={(e) => setRecoveryReason(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "8px",
                    backgroundColor: "#0d131f",
                    border: "1px solid #374151",
                    color: "#f8fafc",
                    fontSize: "0.85rem"
                  }}
                >
                  <option value="ACCOUNT_COMPROMISE">Private Key Compromise / Extraction</option>
                  <option value="LOST_ACCESS">Device Hardware Loss / Theft</option>
                  <option value="SUSPECTED_FRAUD">Suspicious Cryptographic Activity</option>
                  <option value="ROUTINE_ROTATION">Scheduled Key Lifecycle Rotation</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: "0.8rem", color: "#94a3b8", display: "block", marginBottom: "6px" }}>
                  Additional Incident Details (Optional):
                </label>
                <input
                  type="text"
                  placeholder="e.g. Device lost while traveling abroad"
                  value={customReason}
                  onChange={(e) => setCustomReason(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "8px",
                    backgroundColor: "#0d131f",
                    border: "1px solid #374151",
                    color: "#f8fafc",
                    fontSize: "0.85rem",
                    boxSizing: "border-box"
                  }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "6px" }}>
                <button
                  type="button"
                  onClick={() => setShowRecoveryModal(false)}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "8px",
                    backgroundColor: "#1f2937",
                    border: "1px solid #374151",
                    color: "#94a3b8",
                    fontSize: "0.85rem",
                    cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingRecovery || !recoveryCanStart}
                  style={{
                    padding: "8px 18px",
                    borderRadius: "8px",
                    backgroundColor: "#dc2626",
                    border: "none",
                    color: "#ffffff",
                    fontSize: "0.85rem",
                    fontWeight: 700,
                    cursor: submittingRecovery || !recoveryCanStart ? "not-allowed" : "pointer",
                    opacity: recoveryCanStart ? 1 : 0.55
                  }}
                >
                  {submittingRecovery ? "Creating request..." : "Create Recovery Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
};
