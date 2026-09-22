import React from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { ShieldAlert, ArrowRight, CheckCircle2, Clock } from "lucide-react";

export const RecoveryRequestsPage: React.FC = () => {
  const navigate = useNavigate();

  const petitions = [
    {
      id: "REC-PETITION-101",
      wallet: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
      ownerName: "Charaf Eddine Bessanane",
      newSuggestedKey: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
      reason: "Private key compromised via public Wi-Fi malware. Holder initiated key rotation.",
      approvalsCount: 2,
      requiredCount: 2,
      status: "APPROVED",
      initiatedAt: "2026-09-22 17:05:00",
      txHash: "0xafd3ff8307041cb44a092d82bf3148c56b0b7f2d0d38c68190519722804eb420"
    }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="BLOCKCHAIN_ANCHORED" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Active Recovery Petitions
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Pending and executed social recovery requests submitted to `EmergencyRecovery.sol`.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {petitions.map((p) => (
          <div
            key={p.id}
            style={{
              backgroundColor: "#111827",
              borderRadius: "16px",
              border: "1px solid #1f2937",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
              <div>
                <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#fbbf24" }}>
                  {p.id}
                </span>
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#ffffff", margin: "2px 0 0 0" }}>
                  Wallet Key Rotation: {p.ownerName}
                </h3>
              </div>
              <StatusChip status={p.status} />
            </div>

            <p style={{ fontSize: "0.85rem", color: "#cbd5e1", margin: 0, lineHeight: 1.5 }}>
              <strong>Stated Reason:</strong> {p.reason}
            </p>

            <div
              style={{
                backgroundColor: "#0d131f",
                padding: "14px",
                borderRadius: "10px",
                border: "1px solid #1f2937",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: "12px",
                fontSize: "0.75rem"
              }}
            >
              <div>
                <span style={{ color: "#94a3b8" }}>Compromised Wallet:</span>
                <div style={{ fontFamily: "var(--font-mono)", color: "#f87171", marginTop: "2px" }}>
                  {p.wallet}
                </div>
              </div>

              <div>
                <span style={{ color: "#94a3b8" }}>Proposed Replacement Key:</span>
                <div style={{ fontFamily: "var(--font-mono)", color: "#34d399", marginTop: "2px" }}>
                  {p.newSuggestedKey}
                </div>
              </div>

              <div>
                <span style={{ color: "#94a3b8" }}>Quorum Progress:</span>
                <div style={{ fontWeight: 700, color: "#fbbf24", marginTop: "2px" }}>
                  {p.approvalsCount} of {p.requiredCount} Guardians Approved
                </div>
              </div>

              <div>
                <span style={{ color: "#94a3b8" }}>On-Chain TX Hash:</span>
                <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>
                  {p.txHash.slice(0, 20)}...
                </div>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => navigate(`/guardian/approve/1`)}
                style={{
                  padding: "8px 16px",
                  borderRadius: "8px",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  border: "none",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                <span>Review & Sign Petition</span>
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
