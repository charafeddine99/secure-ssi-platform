import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { StatusChip } from "../../components/common/StatusChip";
import { RecoveryTimeline, GuardianSigner } from "../../components/guardian/RecoveryTimeline";
import {
  fetchGuardians,
  fetchRecoveryRequests,
  fetchCurrentUserId,
  approveRecoveryPetition,
  RecoveryRequest
} from "../../services/api";
import { ShieldAlert, CheckCircle2, AlertTriangle, ArrowRight, RefreshCw } from "lucide-react";

export const GuardianDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [guardians, setGuardians] = useState<GuardianSigner[]>([]);
  const [petitions, setPetitions] = useState<RecoveryRequest[]>([]);
  const [activePetition, setActivePetition] = useState<RecoveryRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [authorizedGuardianIds, setAuthorizedGuardianIds] = useState<string[]>([]);
  const [authorizedGuardianDids, setAuthorizedGuardianDids] = useState<Record<string, string>>({});

  const loadData = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const [guardianData, petitionData, currentUserId] = await Promise.all([
        fetchGuardians(),
        fetchRecoveryRequests(50),
        fetchCurrentUserId()
      ]);

      const activeAssignments = guardianData.filter(
        (guardian) => guardian.guardian_user_id === currentUserId && guardian.approved === 1
      );
      const assignedWallets = new Set(activeAssignments.map((guardian) => guardian.wallet_address));
      const guardianPetitions = petitionData.filter(
        (petition) => assignedWallets.has(petition.walletId) &&
          (petition.status === "PENDING_APPROVALS" || petition.status === "QUORUM_REACHED" || petition.status === "WAITING_TIMELOCK")
      );
      setPetitions(guardianPetitions);
      const pending = guardianPetitions.find((petition) => petition.status === "PENDING_APPROVALS");
      const selectedPetition = pending || guardianPetitions[0] || null;
      setActivePetition(selectedPetition);
      const selectedGuardianIds = activeAssignments
        .filter((guardian) => guardian.wallet_address === selectedPetition?.walletId)
        .map((guardian) => guardian.guardian_id)
        .filter(Boolean);
      setAuthorizedGuardianIds(selectedGuardianIds);
      setAuthorizedGuardianDids(
        Object.fromEntries(
          activeAssignments
            .filter((guardian) => guardian.wallet_address === selectedPetition?.walletId)
            .map((guardian) => [guardian.guardian_id, guardian.guardian_did]),
        ),
      );

      // Map guardians to signers
      const signers: GuardianSigner[] = activeAssignments.map((g) => ({
        guardianId: g.guardian_id || null,
        walletId: g.wallet_address,
        displayIdentifier: g.guardian_address || g.guardian_did || "Identifier unavailable",
        name: g.guardian_name,
        role: g.guardian_role,
        // The Recovery API reports an aggregate count, not which guardian
        // approved; never infer per-guardian approval from array order/status.
        hasApproved: null,
        approvalDate: g.created_at,
        canApprove: selectedGuardianIds.includes(g.guardian_id)
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
      if (!authorizedGuardianIds.includes(guardianAddr)) {
        throw new Error("This signed-in account is not assigned as that Guardian.");
      }
      if (!activePetition.challenge) {
        throw new Error("The Recovery Service did not provide its active challenge.");
      }
      const guardianDid = authorizedGuardianDids[guardianAddr];
      if (!guardianDid) {
        throw new Error("The assigned Guardian DID is not available for signing.");
      }
      const result = await approveRecoveryPetition(
        activePetition,
        guardianAddr,
        guardianDid,
      );
      setActionSuccess(`Decision recorded by the Recovery Service. Current state: ${result.recovery.status}.`);
      await loadData();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to sign recovery approval.");
    }
  };

  return (
    <div className="role-dashboard role-dashboard--guardian" style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <p className="workspace-eyebrow">Recovery assignments</p>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Recovery approvals
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Review requests for wallets with an active Guardian assignment. Approval signing and recovery key management remain server-managed.
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
          View Assigned Recovery Requests ({petitions.length})
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
            {activePetition.status === "PENDING_APPROVALS" && (
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
                Review & Submit Decision <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Live Quorum Visualizer */}
      <RecoveryTimeline
        requiredThreshold={activePetition?.requiredCount ?? null}
        approvedCount={activePetition?.approvalsCount ?? null}
        totalGuardians={guardians.length}
        guardians={guardians}
        onApprove={activePetition?.status === "PENDING_APPROVALS" ? handleSign : undefined}
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
          {Array.from(new Set(guardians.map((guardian) => guardian.walletId).filter((walletId): walletId is string => Boolean(walletId)))).map((walletId) => (
            <div
              key={walletId}
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
                <div style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.95rem" }}>
                  Wallet assignment
                </div>
                <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "4px" }}>
                  Wallet ID: {walletId}
                </div>
                <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "2px" }}>
                  {guardians.filter((guardian) => guardian.walletId === walletId).length} Guardian assignment(s)
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
                <span>Recovery requests</span>
                <ArrowRight size={14} />
              </button>
            </div>
          ))}
          {guardians.length === 0 && (
            <p style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
              No wallet Guardian assignments are available to this account.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
