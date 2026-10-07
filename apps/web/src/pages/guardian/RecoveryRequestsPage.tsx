import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import {
  fetchRecoveryRequests,
  cancelRecoveryRequest,
  RecoveryRequest,
} from "../../services/api";
import {
  ArrowRight,
  RefreshCw,
  XCircle,
} from "lucide-react";

export const RecoveryRequestsPage: React.FC = () => {
  const navigate = useNavigate();
  const [petitions, setPetitions] = useState<RecoveryRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("ALL");
  const [actionError, setActionError] = useState<string | null>(null);

  const loadPetitions = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const data = await fetchRecoveryRequests(50);
      setPetitions(data);
    } catch {
      setActionError("Failed to fetch recovery requests from Recovery Service.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPetitions();
  }, []);

  const handleCancel = async (requestId: string) => {
    try {
      await cancelRecoveryRequest(requestId);
      await loadPetitions();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to cancel recovery petition.");
    }
  };

  const filteredPetitions = petitions.filter((p) => {
    if (filter === "ALL") return true;
    return p.status === filter;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" />
            <TrustBadge level="BLOCKCHAIN_ANCHORED" />
          </div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Active Recovery Petitions
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            M-of-N Shamir Secret Sharing social recovery consensus and time-locked key rotation.
          </p>
        </div>

        <button
          onClick={loadPetitions}
          style={{
            padding: "8px 14px",
            borderRadius: "8px",
            backgroundColor: "#1f2937",
            border: "1px solid #374151",
            color: "#94a3b8",
            fontSize: "0.8rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh Petitions
        </button>
      </div>

      {actionError && (
        <div
          style={{
            padding: "12px",
            borderRadius: "8px",
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#f87171",
            fontSize: "0.85rem",
          }}
        >
          {actionError}
        </div>
      )}

      {/* Filter Tabs */}
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", borderBottom: "1px solid #1f2937", paddingBottom: "10px" }}>
        {["ALL", "PENDING", "APPROVED", "TIMELOCKED", "EXECUTED", "CANCELLED"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              fontSize: "0.75rem",
              fontWeight: 700,
              border: `1px solid ${filter === f ? "#2563eb" : "#1f2937"}`,
              backgroundColor: filter === f ? "rgba(37, 99, 235, 0.2)" : "#0d131f",
              color: filter === f ? "#60a5fa" : "#94a3b8",
              cursor: "pointer",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#94a3b8", padding: "20px" }}>
          <RefreshCw size={16} className="animate-spin" />
          Loading recovery petitions from Recovery Service...
        </div>
      ) : filteredPetitions.length === 0 ? (
        <div
          style={{
            backgroundColor: "#111827",
            borderRadius: "16px",
            border: "1px solid #1f2937",
            padding: "36px",
            textAlign: "center",
            color: "#94a3b8",
            fontSize: "0.9rem",
          }}
        >
          No recovery petitions found matching status &quot;{filter}&quot;.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {filteredPetitions.map((p) => {
            const quorumMet = p.approvalsCount >= p.requiredCount;
            return (
              <div
                key={p.requestId}
                style={{
                  backgroundColor: "#111827",
                  borderRadius: "16px",
                  border: `1px solid ${quorumMet ? "rgba(16, 185, 129, 0.3)" : "#1f2937"}`,
                  padding: "24px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "16px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
                  <div>
                    <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#fbbf24" }}>
                      {p.requestId}
                    </span>
                    <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#ffffff", margin: "2px 0 0 0" }}>
                      Social Recovery Petition for {p.walletId}
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
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "12px",
                    fontSize: "0.75rem",
                  }}
                >
                  <div>
                    <span style={{ color: "#94a3b8" }}>Target Wallet:</span>
                    <div style={{ fontFamily: "var(--font-mono)", color: "#f87171", marginTop: "2px" }}>
                      {p.walletId}
                    </div>
                  </div>

                  <div>
                    <span style={{ color: "#94a3b8" }}>Quorum Progress:</span>
                    <div style={{ fontWeight: 700, color: quorumMet ? "#34d399" : "#fbbf24", marginTop: "2px" }}>
                      {p.approvalsCount} of {p.requiredCount} Guardians Approved
                    </div>
                  </div>

                  <div>
                    <span style={{ color: "#94a3b8" }}>Created At:</span>
                    <div style={{ color: "#cbd5e1", marginTop: "2px" }}>
                      {new Date(p.createdAt).toLocaleString()}
                    </div>
                  </div>

                  {p.timelockExpiresAt && (
                    <div>
                      <span style={{ color: "#94a3b8" }}>Time-lock Window:</span>
                      <div style={{ color: "#fbbf24", fontWeight: 600, marginTop: "2px" }}>
                        Expires {new Date(p.timelockExpiresAt).toLocaleTimeString()}
                      </div>
                    </div>
                  )}

                  {p.txHash && (
                    <div>
                      <span style={{ color: "#94a3b8" }}>On-Chain TX Hash:</span>
                      <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>
                        {p.txHash.slice(0, 18)}...
                      </div>
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                  {p.status === "PENDING" && (
                    <button
                      onClick={() => navigate(`/guardian/approve/${p.requestId}`)}
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
                        gap: "6px",
                      }}
                    >
                      <span>Review & Sign Petition</span>
                      <ArrowRight size={14} />
                    </button>
                  )}

                  {(p.status === "PENDING" || p.status === "TIMELOCKED") && (
                    <button
                      onClick={() => handleCancel(p.requestId)}
                      style={{
                        padding: "8px 14px",
                        borderRadius: "8px",
                        backgroundColor: "rgba(239, 68, 68, 0.15)",
                        border: "1px solid rgba(239, 68, 68, 0.3)",
                        color: "#f87171",
                        fontSize: "0.85rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <XCircle size={14} />
                      Cancel Petition
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

