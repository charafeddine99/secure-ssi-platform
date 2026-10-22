import React, { useState, useEffect, useCallback } from "react";
import { fetchAuditLogs, BackendAuditLog } from "../../services/api";
import { 
  Search, 
  RefreshCw, 
  Download, 
  ChevronDown, 
  ChevronUp, 
  FileText 
} from "lucide-react";

export const AuditExplorerPage: React.FC = () => {
  const [logs, setLogs] = useState<BackendAuditLog[]>([]);
  const [filterType, setFilterType] = useState<string>("ALL");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | string | null>(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchAuditLogs(filterType, 150);
      setLogs(data || []);
    } catch (error) {
      setLogs([]);
      setLoadError(error instanceof Error ? error.message : "Audit events are unavailable.");
    } finally {
      setLoading(false);
    }
  }, [filterType]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleExportCsv = () => {
    const headers = ["ID", "Event Type", "Actor DID", "Target Wallet", "Risk Score", "Timestamp"];
    const rows = logs.map(l => [
      l.id,
      `"${l.event_type}"`,
      `"${l.actor_did || ""}"`,
      `"${l.target_wallet || ""}"`,
      l.risk_score,
      `"${l.created_at}"`
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `audit_trail_${new Date().toISOString().split("T")[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const filteredLogs = logs.filter((l) => {
    const matchesFilter = filterType === "ALL" || l.event_type.toUpperCase().includes(filterType);
    const matchesSearch = !searchTerm || 
      (l.actor_did && l.actor_did.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (l.target_wallet && l.target_wallet.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (l.event_type && l.event_type.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesFilter && matchesSearch;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <p className="workspace-eyebrow">Administration</p>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Audit Event Explorer
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Events returned by the Identity Service. Anchoring is optional; an event is anchored only when a confirmed receipt is available.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            onClick={handleExportCsv}
            style={{
              padding: "8px 14px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              color: "#e2e8f0",
              fontSize: "0.82rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            <Download size={14} />
            Export CSV
          </button>
          <button
            onClick={loadLogs}
            disabled={loading}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              border: "none",
              color: "#ffffff",
              fontSize: "0.82rem",
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            Sync Logs
          </button>
        </div>
      </div>

      {loadError && <div className="workspace-error" role="alert">{loadError}</div>}

      {/* Filter and Search Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ display: "flex", gap: "6px", overflowX: "auto" }}>
          {["ALL", "CREDENTIAL", "GUARDIAN", "QUARANTINE", "FRAUD", "CONSENT", "ANCHOR"].map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              style={{
                padding: "6px 14px",
                borderRadius: "8px",
                fontSize: "0.75rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: filterType === type ? "#2563eb" : "#111827",
                color: filterType === type ? "#ffffff" : "#94a3b8"
              }}
            >
              {type === "ALL" ? "All Events" : `${type}`}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: "260px" }}>
          <div style={{ position: "relative", width: "100%" }}>
            <Search size={14} style={{ position: "absolute", left: "10px", top: "11px", color: "#64748b" }} />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by DID or Wallet..."
              style={{
                width: "100%",
                padding: "8px 12px 8px 32px",
                borderRadius: "8px",
                backgroundColor: "#111827",
                border: "1px solid #1f2937",
                color: "#ffffff",
                fontSize: "0.78rem"
              }}
            />
          </div>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>
                <th style={{ padding: "10px 12px" }}>#ID</th>
                <th style={{ padding: "10px 12px" }}>Event Type</th>
                <th style={{ padding: "10px 12px" }}>Actor DID</th>
                <th style={{ padding: "10px 12px" }}>Target Wallet</th>
                <th style={{ padding: "10px 12px" }}>Risk signal</th>
                <th style={{ padding: "10px 12px" }}>Timestamp</th>
                <th style={{ padding: "10px 12px", textAlign: "right" }}>Inspect</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((l) => {
                const isExpanded = expandedId === l.id;
                return (
                  <React.Fragment key={l.id}>
                    <tr 
                      onClick={() => setExpandedId(isExpanded ? null : l.id)}
                      style={{ 
                        borderBottom: "1px solid #1f2937", 
                        cursor: "pointer",
                        backgroundColor: isExpanded ? "rgba(37, 99, 235, 0.05)" : "transparent"
                      }}
                    >
                      <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>
                        #{l.id}
                      </td>
                      <td style={{ padding: "12px", fontWeight: 700, color: l.event_type.includes("QUARANTINE") ? "#f87171" : l.event_type.includes("ANCHOR") ? "#c084fc" : "#f8fafc" }}>
                        {l.event_type}
                      </td>
                      <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#94a3b8" }}>
                        {l.actor_did ? `${l.actor_did.slice(0, 20)}...` : "system"}
                      </td>
                      <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#cbd5e1" }}>
                        {l.target_wallet ? `${l.target_wallet.slice(0, 16)}...` : "N/A"}
                      </td>
                      <td style={{ padding: "12px", fontWeight: 600, color: "#94a3b8" }}>
                        {Number.isFinite(l.risk_score) ? `${l.risk_score} (advisory)` : "Not supplied"}
                      </td>
                      <td style={{ padding: "12px", color: "#64748b" }}>
                        {l.created_at ? new Date(l.created_at).toLocaleTimeString() : "Not supplied"}
                      </td>
                      <td style={{ padding: "12px", textAlign: "right", color: "#60a5fa" }}>
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </td>
                    </tr>

                    {/* Expandable JSON Detail Row */}
                    {isExpanded && (
                      <tr style={{ backgroundColor: "#0d131f", borderBottom: "1px solid #1f2937" }}>
                        <td colSpan={7} style={{ padding: "14px 20px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#60a5fa", fontSize: "0.75rem", fontWeight: 700 }}>
                              <FileText size={14} />
                              Event Details:
                            </div>
                            <span style={{ fontSize: "0.7rem", color: "#94a3b8", padding: "2px 8px" }}>
                              Chain receipt is not asserted by this view
                            </span>
                          </div>
                          <pre style={{ margin: 0, padding: "10px", backgroundColor: "#060911", borderRadius: "6px", border: "1px solid #1f2937", color: "#e2e8f0", fontSize: "0.72rem", fontFamily: "var(--font-mono)", overflowX: "auto" }}>
                            {JSON.stringify({
                              event_id: l.id,
                              event_type: l.event_type,
                              actor_did: l.actor_did,
                              target_wallet: l.target_wallet,
                              risk_score: l.risk_score,
                              details: l.details,
                              timestamp: l.created_at
                            }, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
              {!loading && filteredLogs.length === 0 && (
                <tr><td colSpan={7} style={{ padding: "24px 12px", color: "#94a3b8", textAlign: "center" }}>
                  No audit events are available for this filter.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
