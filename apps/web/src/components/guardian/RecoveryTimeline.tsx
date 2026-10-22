import React from "react";
import { CheckCircle2, Clock, Users } from "lucide-react";

export interface GuardianSigner {
  guardianId: string | null;
  walletId?: string;
  displayIdentifier: string;
  name: string;
  role: string;
  hasApproved: boolean | null;
  approvalDate?: string;
  txHash?: string;
  canApprove?: boolean;
}

interface RecoveryTimelineProps {
  requiredThreshold: number | null;
  approvedCount?: number | null;
  totalGuardians?: number;    // e.g. 3 or 5
  guardians: GuardianSigner[];
  timeLockRemainingHours?: number;
  onApprove?: (guardianAddress: string) => void;
}

export const RecoveryTimeline: React.FC<RecoveryTimelineProps> = ({
  requiredThreshold,
  approvedCount: reportedApprovedCount,
  guardians,
  onApprove
}) => {
  const guardianStatesKnown = guardians.every((guardian) => guardian.hasApproved !== null);
  const approvedCount = reportedApprovedCount ?? (
    guardianStatesKnown ? guardians.filter((guardian) => guardian.hasApproved === true).length : null
  );
  const quorumKnown = approvedCount !== null && requiredThreshold !== null && requiredThreshold > 0;
  const isQuorumReached = quorumKnown && approvedCount >= requiredThreshold;
  const progressPercent = quorumKnown ? Math.min(100, (approvedCount / requiredThreshold) * 100) : 0;

  return (
    <div
      style={{
        backgroundColor: "#111827",
        borderRadius: "14px",
        border: isQuorumReached ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid #1f2937",
        padding: "18px",
        display: "flex",
        flexDirection: "column",
        gap: "14px"
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Users size={18} color="#60a5fa" />
          <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f8fafc" }}>
            Guardian Recovery Quorum
          </span>
        </div>
        <span
          style={{
            fontSize: "0.75rem",
            fontWeight: 700,
            padding: "3px 10px",
            borderRadius: "9999px",
            backgroundColor: isQuorumReached ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)",
            color: isQuorumReached ? "#34d399" : "#fbbf24",
            border: isQuorumReached ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid rgba(245, 158, 11, 0.3)"
          }}
        >
          {isQuorumReached
            ? "QUORUM MET"
            : quorumKnown
              ? `${approvedCount} of ${requiredThreshold} Approvals`
              : "Approval progress unavailable"}
        </span>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: "100%",
          height: "8px",
          backgroundColor: "#1f2937",
          borderRadius: "9999px",
          overflow: "hidden"
        }}
      >
        <div
          style={{
            width: `${progressPercent}%`,
            height: "100%",
            backgroundColor: isQuorumReached ? "#10b981" : "#3b82f6",
            transition: "width 0.3s ease"
          }}
        />
      </div>

      {/* Guardian list */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {guardians.map((g, index) => (
          <div
            key={g.guardianId || `${g.displayIdentifier}-${index}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 12px",
              borderRadius: "8px",
              backgroundColor: "#0d131f",
              border: g.hasApproved === true ? "1px solid rgba(16, 185, 129, 0.25)" : "1px solid #1f2937"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {g.hasApproved === true ? (
                <CheckCircle2 size={18} color="#34d399" />
              ) : (
                <Clock size={18} color="#94a3b8" />
              )}
              <div>
                <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#f8fafc" }}>
                  {g.name} <span style={{ fontSize: "0.7rem", color: "#64748b" }}>({g.role})</span>
                </div>
                <div style={{ fontSize: "0.7rem", fontFamily: "var(--font-mono)", color: "#94a3b8" }}>
                  {g.displayIdentifier}
                </div>
              </div>
            </div>

            <div>
              {g.hasApproved === true ? (
                <span style={{ fontSize: "0.72rem", color: "#34d399", fontWeight: 600 }}>
                  Signed
                </span>
              ) : onApprove && g.guardianId && g.canApprove ? (
                <button
                  onClick={() => onApprove(g.guardianId!)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    backgroundColor: "#2563eb",
                    color: "#ffffff",
                    border: "none",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer"
                  }}
                >
                  Submit decision
                </button>
              ) : (
                <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                  {g.hasApproved === false ? "Pending" : "Not assigned to this account"}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
