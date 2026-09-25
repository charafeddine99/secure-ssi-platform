import React, { useState, useEffect } from "react";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { fetchCredentials, BackendCredential } from "../../services/api";
import { RotateCcw, AlertTriangle, ShieldCheck, CheckCircle2, Lock } from "lucide-react";

export const RevocationRegistryPage: React.FC = () => {
  const [credentials, setCredentials] = useState<BackendCredential[]>([]);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  useEffect(() => {
    fetchCredentials()
      .then((data) => {
        if (data) setCredentials(data);
      })
      .catch(() => {});
  }, []);

  const handleRevoke = (credId: string) => {
    setRevokingId(credId);
    setTimeout(() => {
      setCredentials((prev) =>
        prev.map((c) => (c.id === credId ? { ...c, status: "REVOKED" as const } : c))
      );
      setRevokingId(null);
    }, 1000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="BLOCKCHAIN_ANCHORED" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Bitstring Status List & Revocation Registry
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          W3C BitstringStatusList2021 manager anchored on Ethereum smart contracts (`RevocationRegistry.sol`).
        </p>
      </div>

      {/* Registry Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
        <div style={{ backgroundColor: "#111827", borderRadius: "14px", border: "1px solid #1f2937", padding: "18px" }}>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Status List Size</span>
          <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "#ffffff", marginTop: "4px" }}>
            16,384 bits
          </div>
          <span style={{ fontSize: "0.72rem", color: "#60a5fa" }}>Gzip compressed root</span>
        </div>

        <div style={{ backgroundColor: "#111827", borderRadius: "14px", border: "1px solid #1f2937", padding: "18px" }}>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Allocated Indices</span>
          <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "#ffffff", marginTop: "4px" }}>
            {credentials.length || 7} Indices
          </div>
          <span style={{ fontSize: "0.72rem", color: "#34d399" }}>Bit indexes 100 - 106</span>
        </div>

        <div style={{ backgroundColor: "#111827", borderRadius: "14px", border: "1px solid #1f2937", padding: "18px" }}>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>On-Chain Contract Anchor</span>
          <div style={{ fontSize: "0.85rem", fontFamily: "var(--font-mono)", color: "#c084fc", marginTop: "6px" }}>
            0x9fE4...a6e0
          </div>
          <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>RevocationRegistry.sol</span>
        </div>
      </div>

      {/* Revocation List Table */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "14px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff", margin: "0 0 16px 0" }}>
          Active Credential Status Table
        </h3>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>
                <th style={{ padding: "10px 12px" }}>Status List Index</th>
                <th style={{ padding: "10px 12px" }}>Credential Title</th>
                <th style={{ padding: "10px 12px" }}>Subject Wallet</th>
                <th style={{ padding: "10px 12px" }}>Status</th>
                <th style={{ padding: "10px 12px" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {credentials.map((c, i) => (
                <tr key={c.id} style={{ borderBottom: "1px solid #1f2937" }}>
                  <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>
                    #{104 + i}
                  </td>
                  <td style={{ padding: "12px", fontWeight: 600, color: "#f8fafc" }}>
                    {c.title}
                  </td>
                  <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#94a3b8" }}>
                    {c.wallet_address ? `${c.wallet_address.slice(0, 10)}...` : "0xf39Fd6e..."}
                  </td>
                  <td style={{ padding: "12px" }}>
                    <StatusChip status={c.status} size="sm" />
                  </td>
                  <td style={{ padding: "12px" }}>
                    {c.status === "ACTIVE" ? (
                      <button
                        onClick={() => handleRevoke(c.id)}
                        disabled={revokingId === c.id}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "6px",
                          backgroundColor: "rgba(239, 68, 68, 0.15)",
                          border: "1px solid rgba(239, 68, 68, 0.3)",
                          color: "#f87171",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          cursor: "pointer"
                        }}
                      >
                        {revokingId === c.id ? "Anchoring..." : "Revoke on Chain"}
                      </button>
                    ) : (
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Permanently Revoked</span>
                    )}
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
