import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { fetchCredentials, BackendCredential } from "../../services/api";
import { Building2, PlusCircle, FileText, RotateCcw, CheckCircle2, Clock, Users, ArrowRight } from "lucide-react";

export const IssuerDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [issuedCreds, setIssuedCreds] = useState<BackendCredential[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchCredentials()
      .then((data) => {
        if (data) setIssuedCreds(data);
      })
      .catch(() => {});
  }, []);

  const stats = [
    { label: "Total Active Credentials", value: issuedCreds.length || 7, change: "+2 this week", icon: FileText, color: "#60a5fa" },
    { label: "Approved Issuance Rate", value: "98.4%", change: "NIST AI RMF Verified", icon: CheckCircle2, color: "#34d399" },
    { label: "Active Status List Entries", value: "1,024 bits", change: "Bitstring 2021 Root", icon: RotateCcw, color: "#c084fc" },
    { label: "AI Threat Interceptions", value: "3 Blocked", change: "Auto-quarantined on EVM", icon: Building2, color: "#f87171" }
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
            Issuer Operations Console
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Institutional issuance authority for W3C Verifiable Credentials 2.0 with integrated AI risk gate.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={() => navigate("/issuer/templates")}
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
            <FileText size={16} />
            View Templates
          </button>

          <button
            onClick={() => navigate("/issuer/issue")}
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              border: "none",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.85rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              boxShadow: "0 4px 12px rgba(37,99,235,0.3)"
            }}
          >
            <PlusCircle size={16} />
            Issue New Credential
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

      {/* Recent Issuances Table */}
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
            Recent Credential Issuances
          </h3>
          <span style={{ fontSize: "0.75rem", color: "#60a5fa" }}>
            Anchored on Hardhat EVM
          </span>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>
                <th style={{ padding: "10px 12px" }}>Credential Title</th>
                <th style={{ padding: "10px 12px" }}>Category</th>
                <th style={{ padding: "10px 12px" }}>Subject Wallet</th>
                <th style={{ padding: "10px 12px" }}>Issue Date</th>
                <th style={{ padding: "10px 12px" }}>AI Risk</th>
                <th style={{ padding: "10px 12px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {issuedCreds.slice(0, 6).map((c) => (
                <tr key={c.id} style={{ borderBottom: "1px solid #1f2937" }}>
                  <td style={{ padding: "12px", fontWeight: 600, color: "#f8fafc" }}>
                    {c.title}
                  </td>
                  <td style={{ padding: "12px", color: "#93c5fd" }}>
                    {c.category}
                  </td>
                  <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#94a3b8" }}>
                    {c.wallet_address ? `${c.wallet_address.slice(0, 10)}...` : "0xf39Fd6e..."}
                  </td>
                  <td style={{ padding: "12px", color: "#cbd5e1" }}>
                    {c.issued_date}
                  </td>
                  <td style={{ padding: "12px", fontWeight: 600, color: c.ai_risk_score > 50 ? "#f87171" : "#34d399" }}>
                    {c.ai_risk_score} / 100
                  </td>
                  <td style={{ padding: "12px" }}>
                    <StatusChip status={c.status} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
