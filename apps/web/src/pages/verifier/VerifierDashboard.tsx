import React from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { Search, PlusCircle, FileCheck, History, CheckCircle2, ShieldCheck, ArrowRight } from "lucide-react";

export const VerifierDashboard: React.FC = () => {
  const navigate = useNavigate();

  const stats = [
    { label: "Total Presentations Audited", value: "148", change: "100% Cryptographic", icon: FileCheck, color: "#34d399" },
    { label: "Average Verification Latency", value: "0.14 ms", change: "Local ed25519-2020", icon: Search, color: "#60a5fa" },
    { label: "Selective Disclosure Rate", value: "86.2%", change: "Zero Data Leakage", icon: ShieldCheck, color: "#c084fc" },
    { label: "Revoked / Expired Interceptions", value: "4 Rejected", change: "Bitstring verified", icon: History, color: "#f87171" }
  ];

  const recentVerifications = [
    {
      id: "VP-9021",
      subject: "Charaf Eddine Bessanane",
      verifierType: "Airport Transit Border Check",
      claimsVerified: ["Nationality: TUR", "Predicate: age >= 18"],
      hiddenClaimsCount: 4,
      status: "VERIFIED",
      timestamp: "10 mins ago"
    },
    {
      id: "VP-9020",
      subject: "Charaf Eddine Bessanane",
      verifierType: "Open Banking KYC Audit",
      claimsVerified: ["Account Holder", "Tax ID", "AML Status"],
      hiddenClaimsCount: 1,
      status: "VERIFIED",
      timestamp: "1 hour ago"
    },
    {
      id: "VP-9019",
      subject: "Anonymous Holder",
      verifierType: "Campus Lab Access Gate",
      claimsVerified: ["Enrollment: ACTIVE"],
      hiddenClaimsCount: 6,
      status: "VERIFIED",
      timestamp: "Yesterday"
    }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" />
            <TrustBadge level="DEMO_TRUST_LEVEL" />
          </div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Verifier Trust Console
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            High-speed cryptographic verification of W3C Verifiable Presentations and selective disclosures.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={() => navigate("/verifier/request")}
            style={{
              padding: "10px 16px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              color: "#e2e8f0",
              fontWeight: 600,
              fontSize: "0.85rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            <PlusCircle size={16} />
            New Request
          </button>

          <button
            onClick={() => navigate("/verifier/verify")}
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              backgroundColor: "#059669",
              border: "none",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.85rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              boxShadow: "0 4px 12px rgba(5,150,105,0.3)"
            }}
          >
            <Search size={16} />
            Verify Presentation Live
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
        {stats.map((s, i) => {
          const Icon = s.icon;
          return (
            <div
              key={i}
              style={{
                backgroundColor: "#111827",
                borderRadius: "14px",
                border: "1px solid #1f2937",
                padding: "20px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <span style={{ fontSize: "0.75rem", color: "#94a3b8", fontWeight: 600 }}>{s.label}</span>
                <Icon size={18} color={s.color} />
              </div>
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", lineHeight: 1 }}>
                {s.value}
              </div>
              <div style={{ fontSize: "0.72rem", color: s.color, marginTop: "8px", fontWeight: 500 }}>
                {s.change}
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent Verifications */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "14px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
            Recent Presentation Audits
          </h3>
          <span style={{ fontSize: "0.75rem", color: "#34d399" }}>
            Real-time Verification Stream
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {recentVerifications.map((v) => (
            <div
              key={v.id}
              style={{
                backgroundColor: "#0d131f",
                borderRadius: "10px",
                border: "1px solid #1f2937",
                padding: "14px 16px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "12px"
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.9rem" }}>
                    {v.verifierType}
                  </span>
                  <StatusChip status={v.status} size="sm" />
                </div>
                <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "4px" }}>
                  Subject: {v.subject} • Verified: {v.claimsVerified.join(", ")}
                </div>
                <div style={{ fontSize: "0.72rem", color: "#34d399", marginTop: "2px" }}>
                  Minimization: {v.hiddenClaimsCount} sensitive fields completely hidden via salted blind commitment
                </div>
              </div>

              <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#64748b" }}>
                <div>{v.timestamp}</div>
                <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{v.id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
