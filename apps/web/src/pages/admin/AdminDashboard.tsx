import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { StatusChip } from "../../components/common/StatusChip";
import { 
  fetchGatewayStatus, 
  fetchBlockchainStatus, 
  fetchBlockchainContracts,
  fetchFraudStats,
  fetchDatabaseStats,
  fetchAuditLogs,
  GatewayStatus, 
  BlockchainStatus,
  SmartContractInfo,
  FraudModelStats
} from "../../services/api";
import { 
  Settings, 
  Database, 
  History, 
  Cpu, 
  RefreshCw, 
  Server, 
  ArrowRight,
  Download,
  CheckCircle2,
  HardDrive
} from "lucide-react";

interface DbStatsInfo {
  active_runtime?: string;
  credentials?: number;
  audit_logs?: number;
  users?: number;
  guardians?: number;
  sqlite_fallback_stats?: {
    users?: number;
    credentials?: number;
    guardians?: number;
    audit_logs?: number;
  };
  stats?: {
    users?: number;
    credentials?: number;
    guardians?: number;
    audit_logs?: number;
  };
}

export const AdminDashboard: React.FC = () => {
  const [gateway, setGateway] = useState<GatewayStatus | null>(null);
  const [blockchain, setBlockchain] = useState<BlockchainStatus | null>(null);
  const [contracts, setContracts] = useState<SmartContractInfo[]>([]);
  const [fraudStats, setFraudStats] = useState<FraudModelStats | null>(null);
  const [dbStats, setDbStats] = useState<DbStatsInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const [gw, bc, contractDirectory, fs, ds] = await Promise.all([
        fetchGatewayStatus().catch(() => null),
        fetchBlockchainStatus().catch(() => null),
        fetchBlockchainContracts().catch(() => []),
        fetchFraudStats().catch(() => null),
        fetchDatabaseStats().catch(() => null)
      ]);
      setGateway(gw);
      setBlockchain(bc || gw?.blockchain || null);
      setContracts(contractDirectory);
      setFraudStats(fs);
      setDbStats((ds as DbStatsInfo | null) || (gw?.database as DbStatsInfo | null) || null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleExportAuditJson = async () => {
    try {
      const logs = await fetchAuditLogs("ALL", 200);
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(logs, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `secure_ssi_audit_trail_${new Date().toISOString().split("T")[0]}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      setActionNotice("Audit trail JSON exported successfully.");
      setTimeout(() => setActionNotice(null), 4000);
    } catch {
      setActionNotice("Failed to export audit trail.");
      setTimeout(() => setActionNotice(null), 4000);
    }
  };

  const microservices = [
    { 
      name: "API Gateway & Proxy", 
      port: 8000, 
      status: gateway?.gateway_status || "UNKNOWN",
      role: "Central Ingress, CORS, & Context Propagation" 
    },
    { 
      name: "SSI Core & Identity Service", 
      port: 8001, 
      status: gateway?.services?.identity_service || "UNKNOWN",
      role: "W3C VC 2.0, Ed25519 & Bitstring Status List" 
    },
    { 
      name: "Risk Evaluation Service",
      port: 8002, 
      status: gateway?.services?.fraud_service || "UNKNOWN",
      role: "Deterministic advisory risk heuristic"
    },
    { 
      name: "Social Recovery Service", 
      port: 8003, 
      status: gateway?.services?.recovery_service || "UNKNOWN",
      role: "Guardian recovery service"
    },
    { 
      name: "Ethereum Hardhat Node", 
      port: 8545, 
      status: blockchain ? (blockchain.connected ? "ONLINE" : "OFFLINE") : "UNKNOWN",
      role: blockchain
        ? `${blockchain.network || "Network not reported"} • Chain ${blockchain.chainId ?? "unknown"}`
        : "Optional integrity anchor; status unavailable"
    }
  ];

  const dbCounts = dbStats?.sqlite_fallback_stats || dbStats?.stats || dbStats;

  return (
    <div className="admin-dashboard">
      {/* Top Header */}
      <div className="admin-dashboard__header">
        <div>
          <p className="admin-dashboard__eyebrow">Platform administration</p>
          <h1>Administration</h1>
          <p className="admin-dashboard__description">
            Service health, audit records and optional EVM telemetry.
          </p>
        </div>

        <div className="admin-dashboard__header-actions">
          <button
            onClick={loadStatus}
            disabled={loading}
            className="workspace-secondary-action"
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            Refresh Telemetry
          </button>
        </div>
      </div>

      {actionNotice && (
        <div className="admin-dashboard__notice" role="status">
          <CheckCircle2 size={16} />
          {actionNotice}
        </div>
      )}

      {/* Microservice Health Matrix */}
      <div
        className="admin-dashboard__health-panel"
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div className="admin-dashboard__section-heading">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Server size={18} color="#60a5fa" />
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
              Connected Platform Microservices
            </h3>
          </div>
          <span className="admin-dashboard__system-health">
            System Health: {gateway?.system_health || "UNKNOWN"}
          </span>
        </div>

        <div className="admin-dashboard__service-grid">
          {microservices.map((m) => (
            <div
              key={m.name}
              className="admin-dashboard__service-card"
              style={{
                backgroundColor: "#0d131f",
                borderRadius: "10px",
                border: "1px solid #1f2937",
                padding: "14px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="admin-dashboard__service-name">
                  {m.name}
                </span>
                <StatusChip status={m.status} size="sm" />
              </div>
              <div className="admin-dashboard__service-port">
                Port :{m.port}
              </div>
              <div className="admin-dashboard__service-description">
                {m.role}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Operational Deep-Dive Cards: Database, Blockchain, AI Engine */}
      <div className="admin-dashboard__detail-grid">
        {/* 1. Database & Persistence Layer */}
        <div className="admin-dashboard__detail-card">
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#38bdf8", marginBottom: "12px" }}>
            <HardDrive size={18} />
            <h4 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
              Authoritative Persistence Layer
            </h4>
          </div>
          <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: "12px" }}>
            Persistence telemetry
            <br />
            Active Runtime: <span style={{ color: "#34d399", fontWeight: 600 }}>{String(dbStats?.active_runtime || "Unknown")}</span>
          </div>

          <div className="admin-dashboard__metric-grid">
            <div className="admin-dashboard__metric">
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>Persisted VCs</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#f8fafc" }}>{dbCounts?.credentials ?? "—"}</div>
            </div>
            <div className="admin-dashboard__metric">
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>Audit Events</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#f8fafc" }}>{dbCounts?.audit_logs ?? "—"}</div>
            </div>
            <div className="admin-dashboard__metric">
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>Registered DIDs</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#f8fafc" }}>{dbCounts?.users ?? "—"}</div>
            </div>
            <div className="admin-dashboard__metric">
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>Enrolled Guardians</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#f8fafc" }}>{dbCounts?.guardians ?? "—"}</div>
            </div>
          </div>
        </div>

        {/* 2. Blockchain EVM Node */}
        <div className="admin-dashboard__detail-card">
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#c084fc", marginBottom: "12px" }}>
            <Database size={18} />
            <h4 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
              Optional Blockchain Integrity Anchor
            </h4>
          </div>
          <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: "12px" }}>
            Network: <span style={{ color: "#c084fc", fontWeight: 600 }}>{blockchain?.network || "Not reported"}</span>
            <br />
            Chain ID: <span style={{ color: "#c084fc", fontWeight: 600 }}>{blockchain?.chainId ?? "Not reported"}</span>
            <br />
            Current Height: <span style={{ color: "#34d399", fontWeight: 600 }}>{blockchain?.connected && blockchain.currentBlockNumber != null ? `Block #${blockchain.currentBlockNumber}` : "Unavailable"}</span>
            <br />
            Connection: <span style={{ color: blockchain?.connected ? "#34d399" : "#fbbf24" }}>{blockchain ? (blockchain.connected ? "Connected" : "Offline / unavailable") : "Unknown"}</span>
          </div>

          <div className="admin-dashboard__contract-list">
            {contracts.length === 0 && <p style={{ color: "#94a3b8", fontSize: "0.75rem" }}>No contract directory response is available.</p>}
            {contracts.map((c) => (
              <div key={c.name} className="admin-dashboard__contract-row">
                <span className="admin-dashboard__contract-name">{c.name}</span>
                <code className="admin-dashboard__contract-address">{c.address || "Not configured"}</code>
                <span className="admin-dashboard__contract-status">{c.status || "Unknown"}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 3. Risk evaluation service metadata */}
        <div className="admin-dashboard__detail-card">
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#f87171", marginBottom: "12px" }}>
            <Cpu size={18} />
            <h4 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
              Risk Evaluation Service
            </h4>
          </div>
          <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: "12px" }}>
            {fraudStats?.model_type || "Risk heuristic unavailable"} · version {fraudStats?.model_version || "—"}
          </div>
          <div className="admin-dashboard__risk-grid">
            <div className="admin-dashboard__metric">
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>Training status</div>
              <div style={{ fontSize: "0.9rem", fontWeight: 800, color: "#fbbf24" }}>{fraudStats?.model_status || "UNKNOWN"}</div>
            </div>
            <div className="admin-dashboard__metric">
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>Evaluation</div>
              <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#f8fafc" }}>{fraudStats?.evaluation_status || "Not reported"}</div>
            </div>
            <div className="admin-dashboard__metric admin-dashboard__metric--wide">
              <div style={{ fontSize: "0.7rem", color: "#64748b" }}>Configured signals</div>
              <div style={{ fontSize: "0.72rem", color: "#cbd5e1", marginTop: "4px" }}>{fraudStats?.risk_signals?.join(" · ") || "Unavailable"}</div>
              <div style={{ fontSize: "0.68rem", color: "#fbbf24", marginTop: "5px" }}>{fraudStats?.dataset_label || "Dataset not reported"} · advisory only</div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="admin-dashboard__action-grid">
        <Link
          to="/admin/contracts"
          className="admin-dashboard__action-card portal-card-hover"
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
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#c084fc", marginBottom: "8px" }}>
              <Database size={20} />
              <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                Smart Contracts Registry
              </h4>
            </div>
            <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: 0, lineHeight: 1.5 }}>
              View configured contract addresses and receipt-backed anchor records. Contract deployment is reported only when checked against a connected node.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "16px", color: "#c084fc", fontSize: "0.8rem", fontWeight: 700 }}>
            <span>Inspect Contracts</span>
            <ArrowRight size={14} />
          </div>
        </Link>

        <Link
          to="/admin/audit"
          className="admin-dashboard__action-card portal-card-hover"
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
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#38bdf8", marginBottom: "8px" }}>
              <History size={20} />
              <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                Audit Event Viewer
              </h4>
            </div>
            <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: 0, lineHeight: 1.5 }}>
              Browse audit events returned by the service. This view does not certify immutable storage or compliance.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "16px", color: "#38bdf8", fontSize: "0.8rem", fontWeight: 700 }}>
            <span>Explore Logs</span>
            <ArrowRight size={14} />
          </div>
        </Link>

        <Link
          to="/admin/fraud-monitor"
          className="admin-dashboard__action-card portal-card-hover"
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
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#f87171", marginBottom: "8px" }}>
              <Cpu size={20} />
              <h4 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                Synthetic Risk Heuristic
              </h4>
            </div>
            <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: 0, lineHeight: 1.5 }}>
              Inspect versioned rule-based risk signals. Scores are advisory and do not establish credential trust or validity.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "16px", color: "#f87171", fontSize: "0.8rem", fontWeight: 700 }}>
            <span>View Threat Stream</span>
            <ArrowRight size={14} />
          </div>
        </Link>
      </div>

      {/* Admin Quick System Tools */}
      <div className="admin-dashboard__tools">
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Settings size={18} color="#94a3b8" />
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#ffffff" }}>Audit tools</span>
        </div>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button
            onClick={handleExportAuditJson}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              color: "#e2e8f0",
              fontSize: "0.78rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            <Download size={13} />
            Export Audit Trail (JSON)
          </button>
        </div>
      </div>
    </div>
  );
};
