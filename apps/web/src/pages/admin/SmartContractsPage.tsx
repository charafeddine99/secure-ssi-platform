import React, { useCallback, useEffect, useState } from "react";
import { Clock, Database, RefreshCw } from "lucide-react";
import {
  fetchBlockchainAnchors,
  fetchBlockchainContracts,
  fetchBlockchainStatus,
  BlockchainStatus,
  OnChainAnchor,
  SmartContractInfo,
} from "../../services/api";

export const SmartContractsPage: React.FC = () => {
  const [status, setStatus] = useState<BlockchainStatus | null>(null);
  const [contracts, setContracts] = useState<SmartContractInfo[]>([]);
  const [anchors, setAnchors] = useState<OnChainAnchor[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [network, configuredContracts, recentAnchors] = await Promise.all([
        fetchBlockchainStatus(),
        fetchBlockchainContracts(),
        fetchBlockchainAnchors(15),
      ]);
      setStatus(network);
      setContracts(configuredContracts);
      setAnchors(recentAnchors);
      if (!network) setError("Optional EVM status is unavailable.");
    } catch {
      setStatus(null);
      setContracts([]);
      setAnchors([]);
      setError("Blockchain telemetry could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const confirmedAnchors = anchors.filter(
    (anchor) => anchor.status === "CONFIRMED" && Boolean(anchor.txHash),
  );

  return (
    <main style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <p className="workspace-eyebrow">Administration</p>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#fff", margin: 0 }}>
            Optional EVM integrity evidence
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "6px 0 0" }}>
            Chain state is separate from credential trust, proof validity, and status-list decisions.
          </p>
        </div>
        <button type="button" onClick={() => void loadData()} disabled={loading} style={{ padding: "8px 14px", borderRadius: "8px", border: "1px solid #374151", background: "#1f2937", color: "#e2e8f0", display: "flex", alignItems: "center", gap: "7px", cursor: loading ? "wait" : "pointer" }}>
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          Refresh telemetry
        </button>
      </header>

      {error && <div role="status" style={{ color: "#fbbf24", background: "#2a2110", border: "1px solid #854d0e", borderRadius: "8px", padding: "12px" }}>{error}</div>}

      <section aria-label="Optional network status" style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: "14px", padding: "18px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "16px" }}>
        <div>
          <div style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Connection</div>
          <div style={{ color: status?.connected ? "#34d399" : "#cbd5e1", fontWeight: 700, marginTop: "4px" }}>{status ? (status.connected ? "Connected" : "Offline / unavailable") : "Unknown"}</div>
        </div>
        <div>
          <div style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Network</div>
          <div style={{ color: "#f8fafc", fontWeight: 700, marginTop: "4px" }}>{status?.network || "Not reported"}</div>
        </div>
        <div>
          <div style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Chain ID</div>
          <div style={{ color: "#f8fafc", fontWeight: 700, marginTop: "4px" }}>{status?.chainId ?? "Not reported"}</div>
        </div>
        <div>
          <div style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Current block</div>
          <div style={{ color: "#f8fafc", fontWeight: 700, marginTop: "4px" }}>{status?.connected && status.currentBlockNumber != null ? `#${status.currentBlockNumber}` : "Unavailable"}</div>
        </div>
      </section>

      <section style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: "14px", padding: "18px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "9px", marginBottom: "12px" }}>
          <Database size={18} color="#c084fc" />
          <h2 style={{ color: "#f8fafc", fontSize: "1rem", margin: 0 }}>Configured contract directory</h2>
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.8rem", margin: "0 0 14px" }}>
          An address returned by configuration does not prove that a contract is deployed or verified. Connection and receipt evidence are shown separately.
        </p>
        {contracts.length === 0 ? (
          <p style={{ color: "#94a3b8", fontSize: "0.82rem", margin: 0 }}>{loading ? "Loading configured contracts…" : "No contract directory response is available."}</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
            {contracts.map((contract) => (
              <article key={contract.name} style={{ background: "#0d131f", border: "1px solid #1f2937", borderRadius: "10px", padding: "14px" }}>
                <h3 style={{ color: "#f8fafc", fontSize: "0.9rem", margin: "0 0 8px" }}>{contract.name}</h3>
                <div style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Configured address</div>
                <code style={{ color: "#cbd5e1", fontSize: "0.72rem", wordBreak: "break-all" }}>{contract.address || "Not configured"}</code>
                <p style={{ color: "#94a3b8", fontSize: "0.76rem", lineHeight: 1.5 }}>{contract.purpose}</p>
                <div style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Directory status: {contract.status || "Not reported"}</div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: "14px", padding: "18px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "9px", marginBottom: "8px" }}>
          <Clock size={18} color="#c084fc" />
          <h2 style={{ color: "#f8fafc", fontSize: "1rem", margin: 0 }}>Receipt-backed anchors</h2>
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.8rem", margin: "0 0 14px" }}>
          Only records marked CONFIRMED with a transaction hash are shown as confirmed anchors. Other states remain visible as pending, offline, skipped, or failed evidence.
        </p>
        {anchors.length === 0 ? (
          <p style={{ color: "#94a3b8", fontSize: "0.82rem", margin: 0 }}>{loading ? "Loading anchor records…" : "No anchor records were returned by the service."}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {anchors.map((anchor) => {
              const confirmed = confirmedAnchors.includes(anchor);
              return (
                <article key={anchor.anchorId} style={{ background: "#0d131f", border: "1px solid #1f2937", borderRadius: "9px", padding: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
                    <strong style={{ color: "#e2e8f0", fontSize: "0.8rem" }}>{anchor.eventType} · {anchor.contractType}</strong>
                    <span style={{ color: confirmed ? "#34d399" : "#fbbf24", fontSize: "0.75rem", fontWeight: 700 }}>{anchor.status}</span>
                  </div>
                  <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: "5px" }}>Digest: <code style={{ wordBreak: "break-all" }}>{anchor.eventHash}</code></div>
                  <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: "4px" }}>Transaction: {confirmed ? <code>{anchor.txHash}</code> : "No confirmed transaction receipt"}</div>
                  <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: "4px" }}>Block: {confirmed && anchor.blockNumber != null ? anchor.blockNumber : "Not confirmed"} · Created: {new Date(anchor.createdAt).toLocaleString()}</div>
                  {anchor.errorMessage && <div style={{ color: "#fbbf24", fontSize: "0.72rem", marginTop: "4px" }}>{anchor.errorMessage}</div>}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
};
