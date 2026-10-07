import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import {
  fetchRecoveryPolicy,
  fetchGuardians,
  fetchRecoveryRequests,
  initiateRecoveryRequest,
  cancelRecoveryRequest,
  RecoveryPolicy,
  RecoveryRequest,
  BackendGuardian
} from "../../services/api";
import {
  KeyRound,
  Eye,
  EyeOff,
  Users,
  Copy,
  Check,
  AlertTriangle,
  ShieldAlert,
  XCircle,
} from "lucide-react";

export const SecuritySettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [showSeed, setShowSeed] = useState(false);
  const [copied, setCopied] = useState(false);

  // Recovery State
  const [policy, setPolicy] = useState<RecoveryPolicy | null>(null);
  const [guardiansList, setGuardiansList] = useState<BackendGuardian[]>([]);
  const [activePetition, setActivePetition] = useState<RecoveryRequest | null>(null);
  const [showRecoveryModal, setShowRecoveryModal] = useState(false);
  const [recoveryReason, setRecoveryReason] = useState("ACCOUNT_COMPROMISE");
  const [customReason, setCustomReason] = useState("");
  const [submittingRecovery, setSubmittingRecovery] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const seedPhrase = user?.seedPhrase || "apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard";

  const handleCopy = () => {
    navigator.clipboard.writeText(seedPhrase);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const loadRecoveryData = async () => {
    try {
      const walletId = "wallet_holder_primary";
      const [pol, guards, reqs] = await Promise.all([
        fetchRecoveryPolicy(walletId),
        fetchGuardians(),
        fetchRecoveryRequests(10)
      ]);
      setPolicy(pol);
      setGuardiansList(guards);

      const active = reqs.find(
        (r) => r.status === "PENDING" || r.status === "TIMELOCKED" || r.status === "APPROVED"
      );
      setActivePetition(active || null);
    } catch (err: unknown) {
      console.warn("Could not load recovery configuration:", err);
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
      const reasonText = customReason.trim() || recoveryReason;
      const res = await initiateRecoveryRequest({
        walletId: "wallet_holder_primary",
        reason: reasonText
      });
      setStatusMsg({
        type: "success",
        text: `Emergency recovery petition ${res.requestId} successfully created. Guardians notified.`
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
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Sovereign Identity Overview */}
      <div
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
              Sovereign Key Management
            </h2>
          </div>
          <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.8rem" }}>
          <div style={{ backgroundColor: "#0d131f", padding: "10px 12px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ color: "#94a3b8" }}>Decentralized Identifier (DID):</span>
            <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px", wordBreak: "break-all" }}>
              {user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519"}
            </div>
          </div>

          <div style={{ backgroundColor: "#0d131f", padding: "10px 12px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ color: "#94a3b8" }}>EVM Wallet Address:</span>
            <div style={{ fontFamily: "var(--font-mono)", color: "#c084fc", marginTop: "2px" }}>
              {user?.walletAddress || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"}
            </div>
          </div>
        </div>
      </div>

      {statusMsg && (
        <div
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

      {/* 12-Word Seed Backup */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                12-Word Recovery Seed Phrase
              </h3>
              <span
                style={{
                  fontSize: "0.65rem",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  backgroundColor: "#451a03",
                  color: "#f59e0b",
                  border: "1px solid #78350f",
                  fontWeight: 600
                }}
              >
                DEMO ARTIFACT — SIMULATED CUSTODY
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
              Simulated BIP-39 mnemonic phrase for academic evaluation. In production sovereign custody, raw seed phrases are never stored in databases or exposed in plaintext; keys remain in TEE/Secure Enclave hardware with Shamir SSS guardian recovery.
            </p>
          </div>
          <button
            onClick={() => setShowSeed(!showSeed)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 8px",
              borderRadius: "6px",
              border: "1px solid #374151",
              backgroundColor: "#1f2937",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: "0.75rem"
            }}
          >
            {showSeed ? <EyeOff size={14} /> : <Eye size={14} />}
            {showSeed ? "Hide" : "Reveal"}
          </button>
        </div>

        {showSeed ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "8px",
              backgroundColor: "#070a12",
              padding: "14px",
              borderRadius: "10px",
              border: "1px solid #1f2937",
              marginBottom: "12px"
            }}
          >
            {seedPhrase.split(" ").map((w, idx) => (
              <div
                key={idx}
                style={{
                  fontSize: "0.75rem",
                  fontFamily: "var(--font-mono)",
                  color: "#38bdf8",
                  padding: "4px 8px",
                  backgroundColor: "#111827",
                  borderRadius: "6px"
                }}
              >
                <span style={{ color: "#64748b", marginRight: "4px" }}>{idx + 1}.</span>
                {w}
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              backgroundColor: "#070a12",
              padding: "20px",
              borderRadius: "10px",
              border: "1px solid #1f2937",
              textAlign: "center",
              color: "#64748b",
              fontSize: "0.8rem",
              marginBottom: "12px"
            }}
          >
            •••••••• •••••••• •••••••• •••••••• •••••••• ••••••••
          </div>
        )}

        {showSeed && (
          <button
            onClick={handleCopy}
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              color: "#e2e8f0",
              border: "1px solid #374151",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            {copied ? <Check size={14} color="#34d399" /> : <Copy size={14} />}
            {copied ? "Seed Phrase Copied" : "Copy Seed Phrase"}
          </button>
        )}
      </div>

      {/* Social Guardian Recovery (Shamir SSS M-of-N Policy) */}
      <div
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
              Guardian Social Recovery (3-of-5 Shamir Secret Sharing)
            </h3>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "0.7rem", color: "#34d399", fontWeight: 600 }}>
              Threshold: {policy?.minimumApprovals || 3}-of-{policy?.maximumGuardians || 5}
            </span>

            {!activePetition && (
              <button
                onClick={() => setShowRecoveryModal(true)}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  backgroundColor: "#dc2626",
                  color: "#ffffff",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  border: "none",
                  cursor: "pointer",
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
              {policy?.minimumApprovals || 3} of {policy?.maximumGuardians || 5} Signatures
            </div>
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Time-Lock Delay:</span>
            <div style={{ color: "#fbbf24", fontWeight: 600, marginTop: "2px" }}>
              {policy?.timeLockSeconds || 300} seconds (5 min)
            </div>
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Approval Window:</span>
            <div style={{ color: "#34d399", fontWeight: 600, marginTop: "2px" }}>
              {(policy?.approvalWindowSeconds || 3600) / 60} minutes
            </div>
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Anti-Compromise:</span>
            <div style={{ color: "#c084fc", fontWeight: 600, marginTop: "2px" }}>
              Predecessor Key Invalidated
            </div>
          </div>
        </div>

        {/* Guardians List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {guardiansList.map((g, i) => (
            <div
              key={i}
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
                style={{
                  fontSize: "0.68rem",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  backgroundColor: "rgba(16, 185, 129, 0.15)",
                  color: "#34d399",
                  fontWeight: 600
                }}
              >
                ENROLLED (SHAMIR SHARE ACTIVE)
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
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                Initiate Sovereign Social Recovery
              </h3>
            </div>

            <p style={{ fontSize: "0.85rem", color: "#cbd5e1", margin: 0, lineHeight: 1.5 }}>
              Triggering recovery will generate a 128-bit authorization secret challenge. Your assigned guardians must contribute their Shamir polynomial shares. Upon reaching <strong>3-of-5 quorum</strong> and completing the <strong>300s time-lock delay</strong>, your active presentation key will be rotated and marked <code>COMPROMISED</code>.
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
                  disabled={submittingRecovery}
                  style={{
                    padding: "8px 18px",
                    borderRadius: "8px",
                    backgroundColor: "#dc2626",
                    border: "none",
                    color: "#ffffff",
                    fontSize: "0.85rem",
                    fontWeight: 700,
                    cursor: submittingRecovery ? "not-allowed" : "pointer"
                  }}
                >
                  {submittingRecovery ? "Initiating..." : "Confirm & Broadcast Petition"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
