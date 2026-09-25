import React from "react";
import { CheckCircle2, Clock, Users, ShieldAlert } from "lucide-react";

export interface GuardianSigner {
  address: string;
  name: string;
  role: string;
  hasApproved: boolean;
  approvalDate?: string;
  txHash?: string;
}

interface RecoveryTimelineProps {
  requiredThreshold: number; // e.g. 2 or 3
  totalGuardians: number;     // e.g. 3 or 5
  guardians: GuardianSigner[];
  timeLockRemainingHours?: number;
  onApprove?: (guardianAddress: string) => void;
}

export const RecoveryTimeline: React.FC<RecoveryTimelineProps> = ({
  requiredThreshold,
  totalGuardians,
  guardians,
  timeLockRemainingHours = 0,
  onApprove
}) => {
  const approvedCount = guardians.filter((g) => g.hasApproved).length;
  const isQuorumReached = approvedCount >= requiredThreshold;

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
            EIP-4337 Social Recovery Quorum
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
          {isQuorumReached ? "QUORUM MET — KEY ROTATION AUTHORIZED" : `${approvedCount} of ${requiredThreshold} Signatures`}
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
            width: `${Math.min(100, (approvedCount / requiredThreshold) * 100)}%`,
            height: "100%",
            backgroundColor: isQuorumReached ? "#10b981" : "#3b82f6",
            transition: "width 0.3s ease"
          }}
        />
      </div>

      {/* Guardian list */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {guardians.map((g, idx) => (
          <div
            key={g.address}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 12px",
              borderRadius: "8px",
              backgroundColor: "#0d131f",
              border: g.hasApproved ? "1px solid rgba(16, 185, 129, 0.25)" : "1px solid #1f2937"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {g.hasApproved ? (
                <CheckCircle2 size={18} color="#34d399" />
              ) : (
                <Clock size={18} color="#94a3b8" />
              )}
              <div>
                <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#f8fafc" }}>
                  {g.name} <span style={{ fontSize: "0.7rem", color: "#64748b" }}>({g.role})</span>
                </div>
                <div style={{ fontSize: "0.7rem", fontFamily: "var(--font-mono)", color: "#94a3b8" }}>
                  {g.address.slice(0, 10)}...{g.address.slice(-6)}
                </div>
              </div>
            </div>

            <div>
              {g.hasApproved ? (
                <span style={{ fontSize: "0.72rem", color: "#34d399", fontWeight: 600 }}>
                  Signed
                </span>
              ) : onApprove ? (
                <button
                  onClick={() => onApprove(g.address)}
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
                  Sign Approval
                </button>
              ) : (
                <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Pending</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
