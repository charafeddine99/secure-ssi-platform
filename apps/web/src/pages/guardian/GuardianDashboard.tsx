import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { RecoveryTimeline, GuardianSigner } from "../../components/guardian/RecoveryTimeline";
import {
  fetchGuardians,
  fetchRecoveryRequests,
  approveRecoveryPetition,
  BackendGuardian,
  RecoveryRequest
} from "../../services/api";
import { Users, ShieldAlert, CheckCircle2, RotateCcw, AlertTriangle, ArrowRight, RefreshCw, Clock } from "lucide-react";

export const GuardianDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [guardians, setGuardians] = useState<GuardianSigner[]>([]);
  const [petitions, setPetitions] = useState<RecoveryRequest[]>([]);
  const [activePetition, setActivePetition] = useState<RecoveryRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const [guardianData, petitionData] = await Promise.all([
        fetchGuardians(),
        fetchRecoveryRequests(10)
      ]);

      setPetitions(petitionData);
      const pending = petitionData.find(
        (p) => p.status === "PENDING" || p.status === "APPROVED" || p.status === "TIMELOCKED"
      );
      setActivePetition(pending || (petitionData.length > 0 ? petitionData[0] : null));

      // Map guardians to signers
      const signers: GuardianSigner[] = guardianData.map((g, idx) => ({
        address: g.guardian_address || `0x70997970C51812dc3A010C7d01b50e0d17dc79C${idx}`,
        name: g.guardian_name,
        role: g.guardian_role,
        hasApproved: pending ? idx < pending.approvalsCount : g.approved === 1,
        approvalDate: g.created_at,
        txHash: pending?.txHash || undefined
      }));

      setGuardians(signers);
    } catch {
      setActionError("Failed to load guardian network data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSign = async (guardianAddr: string) => {
    if (!activePetition) {
      navigate("/guardian/requests");
      return;
    }
    setActionError(null);
    setActionSuccess(null);
    try {
      await approveRecoveryPetition(activePetition.requestId, guardianAddr);
      setActionSuccess(`Cryptographic approval signed by ${guardianAddr.slice(0, 10)}...`);
      setGuardians((prev) =>
        prev.map((g) => (g.address === guardianAddr ? { ...g, hasApproved: true } : g))
      );
      if (activePetition) {
        setActivePetition({
          ...activePetition,
          approvalsCount: Math.min(activePetition.requiredCount, activePetition.approvalsCount + 1)
        });
      }
    } catch (err: any) {
      setActionError(err.message || "Failed to sign recovery approval.");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" />
            <TrustBadge level="BLOCKCHAIN_ANCHORED" />
            <TrustBadge level="DEMO_TRUST_LEVEL" />
          </div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Guardian Social Recovery Network
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Decentralized sovereign account recovery via 3-of-5 Shamir Secret Sharing multi-sig consensus and time-locked key rotation.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={loadData}
            style={{
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              color: "#94a3b8",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>

          <button
            onClick={() => navigate("/guardian/requests")}
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              backgroundColor: "#d97706",
              border: "none",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.85rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              boxShadow: "0 4px 12px rgba(217,119,6,0.3)"
            }}
          >
            <ShieldAlert size={16} />
            View Active Petitions ({petitions.filter((p) => p.status === "PENDING" || p.status === "TIMELOCKED").length})
          </button>
        </div>
      </div>

      {actionError && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "8px",
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#f87171",
            fontSize: "0.85rem"
          }}
        >
          {actionError}
        </div>
      )}

      {actionSuccess && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "8px",
            backgroundColor: "rgba(16, 185, 129, 0.15)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#34d399",
            fontSize: "0.85rem",
            display: "flex",
            alignItems: "center",
            gap: "8px"
          }}
        >
          <CheckCircle2 size={16} />
          {actionSuccess}
        </div>
      )}

      {/* Active Petition Notice if present */}
      {activePetition && (
        <div
          style={{
            backgroundColor: "#0d131f",
            borderRadius: "12px",
            border: "1px solid #d97706",
            padding: "16px 20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <AlertTriangle size={24} color="#f59e0b" />
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontWeight: 700, color: "#ffffff", fontSize: "0.95rem" }}>
                  Active Recovery Petition: {activePetition.requestId}
                </span>
                <StatusChip status={activePetition.status} size="sm" />
              </div>
              <p style={{ margin: "2px 0 0 0", fontSize: "0.78rem", color: "#94a3b8" }}>
                Target: <code>{activePetition.walletId}</code> — Reason: {activePetition.reason}
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {activePetition.status === "PENDING" && (
              <button
                onClick={() => navigate(`/guardian/approve/${activePetition.requestId}`)}
                style={{
                  padding: "8px 16px",
                  borderRadius: "8px",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  border: "none",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                Review & Sign Petition <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Live Quorum Visualizer */}
      <RecoveryTimeline
        requiredThreshold={activePetition?.requiredCount || 3}
        totalGuardians={guardians.length > 0 ? guardians.length : 5}
        guardians={guardians}
        onApprove={handleSign}
      />

      {/* Protected Wallets Directory */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
            Protected Sovereign Wallets & Guardians
          </h3>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            {guardians.length} Configured Guardians
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div
            style={{
              backgroundColor: "#0d131f",
              borderRadius: "10px",
              border: "1px solid #1f2937",
              padding: "16px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px"
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.95rem" }}>
                  Charaf Eddine Bessanane (Sovereign Holder)
                </span>
                <StatusChip status="ACTIVE" size="sm" />
              </div>
              <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "4px" }}>
                Wallet ID: wallet_holder_primary (0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266)
              </div>
              <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "2px" }}>
                Policy: 3-of-5 Shamir Secret Sharing Quorum — 300s Time-lock Delay
              </div>
            </div>

            <button
              onClick={() => navigate("/guardian/requests")}
              style={{
                padding: "8px 14px",
                borderRadius: "8px",
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                color: "#fbbf24",
                fontSize: "0.8rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px"
              }}
            >
              <span>Recovery Petitions</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
