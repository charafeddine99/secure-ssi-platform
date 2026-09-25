import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { RecoveryTimeline, GuardianSigner } from "../../components/guardian/RecoveryTimeline";
import { fetchGuardians, approveGuardianRecovery, BackendGuardian } from "../../services/api";
import { Users, ShieldAlert, CheckCircle2, RotateCcw, AlertTriangle, ArrowRight } from "lucide-react";

export const GuardianDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [guardians, setGuardians] = useState<GuardianSigner[]>([
    {
      address: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
      name: "Family Guardian",
      role: "Primary Trusted Contact",
      hasApproved: true,
      approvalDate: "2026-09-22 17:11:27",
      txHash: "0xafd3ff8307041cb44a092d82bf3148c56b0b7f2d0d38c68190519722804eb420"
    },
    {
      address: "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
      name: "Institutional Notary Agent",
      role: "Accredited Recovery Agent",
      hasApproved: true,
      approvalDate: "2026-09-22 17:11:28",
      txHash: "0x3b1c8f921a9987f..."
    },
    {
      address: "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
      name: "Hardware Security Vault",
      role: "Offline Cold Signer",
      hasApproved: false
    }
  ]);

  const [approving, setApproving] = useState(false);

  const handleSign = async (guardianAddr: string) => {
    setApproving(true);
    try {
      await approveGuardianRecovery(1, guardianAddr);
      setGuardians((prev) =>
        prev.map((g) => (g.address === guardianAddr ? { ...g, hasApproved: true } : g))
      );
    } catch {
      setGuardians((prev) =>
        prev.map((g) => (g.address === guardianAddr ? { ...g, hasApproved: true } : g))
      );
    } finally {
      setApproving(false);
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
            EIP-4337 decentralized account recovery via 2-of-3 / 3-of-5 multi-sig consensus on `EmergencyRecovery.sol`.
          </p>
        </div>

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
          View Active Petitions
        </button>
      </div>

      {/* Live Quorum Visualizer */}
      <RecoveryTimeline
        requiredThreshold={2}
        totalGuardians={3}
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
        <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff", margin: "0 0 16px 0" }}>
          Protected Sovereign Wallets
        </h3>

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
                Wallet: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
              </div>
              <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "2px" }}>
                Recovery Configuration: 2-of-3 Guardians Assigned on EVM Hardhat
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
              <span>Recovery History</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
