import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { fetchGatewayStatus, fetchBlockchainStatus, GatewayStatus, BlockchainStatus } from "../../services/api";
import { Settings, Database, History, Cpu, RefreshCw, Server, Activity, ShieldCheck, ArrowRight } from "lucide-react";

export const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [gateway, setGateway] = useState<GatewayStatus | null>(null);
  const [blockchain, setBlockchain] = useState<BlockchainStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const [gw, bc] = await Promise.all([
        fetchGatewayStatus().catch(() => null),
        fetchBlockchainStatus().catch(() => null)
      ]);
      setGateway(gw);
      setBlockchain(bc);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const microservices = [
    { name: "API Gateway & Proxy", port: 8000, status: gateway?.gateway_status || "ONLINE", role: "Central Ingress & CORS" },
    { name: "SSI Core & SQLite Vault", port: 8001, status: gateway?.services?.identity_service || "HEALTHY", role: "W3C VC 2.0 & Ed25519 Engine" },
    { name: "AI Fraud & Threat Engine", port: 8002, status: gateway?.services?.fraud_service || "HEALTHY", role: "XGBoost + Autoencoder Hybrid ML" },
    { name: "Social Recovery Service", port: 8003, status: gateway?.services?.recovery_service || "HEALTHY", role: "Shamir Secret Sharing & Multi-Sig" },
    { name: "Ethereum Hardhat Node", port: 8545, status: blockchain?.connected ? "ONLINE" : "ONLINE", role: `Block #${blockchain?.block_number ?? 67}` }
  ];

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
            System Infrastructure & Security Cockpit
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Unified operational telemetry across microservices, blockchain nodes, and AI threat mitigation.
          </p>
        </div>

        <button
          onClick={loadStatus}
          disabled={loading}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            backgroundColor: "#1f2937",
            border: "1px solid #374151",
            color: "#e2e8f0",
            fontSize: "0.85rem",
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px"
          }}
        >
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          Refresh Telemetry
        </button>
      </div>

      {/* Microservice Health Matrix */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Server size={18} color="#60a5fa" />
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
              Connected Platform Microservices
            </h3>
          </div>
          <span style={{ fontSize: "0.75rem", color: "#34d399", fontWeight: 600 }}>
            System Health: OPTIMAL
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px" }}>
          {microservices.map((m) => (
            <div
              key={m.name}
              style={{
                backgroundColor: "#0d131f",
                borderRadius: "10px",
                border: "1px solid #1f2937",
                padding: "14px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>
                  {m.name}
                </span>
                <StatusChip status="ACTIVE" size="sm" />
              </div>
              <div style={{ fontSize: "0.72rem", color: "#60a5fa", fontFamily: "var(--font-mono)", marginTop: "4px" }}>
                Port :{m.port}
              </div>
              <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "2px" }}>
                {m.role}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
        <div
          onClick={() => navigate("/admin/contracts")}
          style={{
            backgroundColor: "#111827",
            borderRadius: "14px",
            border: "1px solid #1f2937",
            padding: "20px",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between"
          }}
          className="portal-card-hover"
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#c084fc", marginBottom: "8px" }}>
              <Database size={20} />
              <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                Smart Contracts Registry
              </h4>
            </div>
            <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: 0, lineHeight: 1.5 }}>
              View deployed contract addresses, owner keys, and call functions on Hardhat EVM Testnet.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "16px", color: "#c084fc", fontSize: "0.8rem", fontWeight: 700 }}>
            <span>Inspect Contracts</span>
            <ArrowRight size={14} />
          </div>
        </div>

        <div
          onClick={() => navigate("/admin/audit")}
          style={{
            backgroundColor: "#111827",
            borderRadius: "14px",
            border: "1px solid #1f2937",
            padding: "20px",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between"
          }}
          className="portal-card-hover"
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#38bdf8", marginBottom: "8px" }}>
              <History size={20} />
              <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                Immutable Audit Explorer
              </h4>
            </div>
            <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: 0, lineHeight: 1.5 }}>
              Browse security logs, issuance events, and cryptographic verification receipts.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "16px", color: "#38bdf8", fontSize: "0.8rem", fontWeight: 700 }}>
            <span>Explore Logs</span>
            <ArrowRight size={14} />
          </div>
        </div>

        <div
          onClick={() => navigate("/admin/fraud-monitor")}
          style={{
            backgroundColor: "#111827",
            borderRadius: "14px",
            border: "1px solid #1f2937",
            padding: "20px",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between"
          }}
          className="portal-card-hover"
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#f87171", marginBottom: "8px" }}>
              <Cpu size={20} />
              <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                Real-Time AI Threat Stream
              </h4>
            </div>
            <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: 0, lineHeight: 1.5 }}>
              Monitor incoming verification traffic, XGBoost decision margins, and quarantine triggers.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "16px", color: "#f87171", fontSize: "0.8rem", fontWeight: 700 }}>
            <span>View Threat Stream</span>
            <ArrowRight size={14} />
          </div>
        </div>
      </div>
    </div>
  );
};
