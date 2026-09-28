import React, { useState, useEffect } from "react";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { fetchCredentials, revokeCredential, BackendCredential } from "../../services/api";
import { AlertTriangle, ShieldCheck, CheckCircle2, Lock, RefreshCw, X } from "lucide-react";

export const RevocationRegistryPage: React.FC = () => {
  const [credentials, setCredentials] = useState<BackendCredential[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Revocation modal state
  const [selectedCred, setSelectedCred] = useState<BackendCredential | null>(null);
  const [revocationReason, setRevocationReason] = useState<string>("AFFILIATION_TERMINATED");
  const [customReason, setCustomReason] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const loadCredentials = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const data = await fetchCredentials();
      if (data) {
        setCredentials(data);
      }
    } catch (err: any) {
      console.warn("Failed to load credentials for revocation registry:", err);
      setError(err?.message || "Failed to load credentials from backend.");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadCredentials();
  }, []);

  const openRevokeModal = (cred: BackendCredential) => {
    setSelectedCred(cred);
    setRevocationReason("AFFILIATION_TERMINATED");
    setCustomReason("");
    setModalError(null);
  };

  const closeRevokeModal = () => {
    if (isSubmitting) return;
    setSelectedCred(null);
    setModalError(null);
  };

  const handleConfirmRevoke = async () => {
    if (!selectedCred) return;
    setIsSubmitting(true);
    setModalError(null);

    const finalReason = revocationReason === "CUSTOM"
      ? (customReason.trim() || "UNSPECIFIED")
      : revocationReason;

    try {
      await revokeCredential(selectedCred.id, finalReason);
      // On success, refresh authoritative state from backend
      await loadCredentials();
      setSelectedCred(null);
    } catch (err: any) {
      console.error("Revocation failed:", err);
      // NEVER silently change UI state if backend revocation failed
      setModalError(err?.message || "Revocation failed on authoritative backend.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeCount = credentials.filter((c) => c.status === "ACTIVE").length;
  const revokedCount = credentials.filter((c) => c.status === "REVOKED").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" />
            <TrustBadge level="BLOCKCHAIN_ANCHORED" />
          </div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Bitstring Status List & Revocation Registry
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Authoritative W3C BitstringStatusList2021 status manager and object-authorized revocation registry.
          </p>
        </div>

        <button
          onClick={loadCredentials}
          disabled={refreshing}
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
          <RefreshCw size={14} className={refreshing ? "spin" : ""} />
          Sync Registry
        </button>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "12px 16px",
          backgroundColor: "rgba(239, 68, 68, 0.15)",
          border: "1px solid rgba(239, 68, 68, 0.4)",
          borderRadius: "8px",
          color: "#fca5a5",
          fontSize: "0.85rem"
        }}>
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Registry Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
        <div style={{ backgroundColor: "#111827", borderRadius: "14px", border: "1px solid #1f2937", padding: "18px" }}>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Status List Specification</span>
          <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#ffffff", marginTop: "4px" }}>
            BitstringStatusList2021
          </div>
          <span style={{ fontSize: "0.72rem", color: "#60a5fa" }}>16,384 bits · Gzip + Base64URL multibase</span>
        </div>

        <div style={{ backgroundColor: "#111827", borderRadius: "14px", border: "1px solid #1f2937", padding: "18px" }}>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Allocated Indices & Status</span>
          <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#ffffff", marginTop: "4px" }}>
            {activeCount} Active / {revokedCount} Revoked
          </div>
          <span style={{ fontSize: "0.72rem", color: "#34d399" }}>{credentials.length} Total Registered</span>
        </div>

        <div style={{ backgroundColor: "#111827", borderRadius: "14px", border: "1px solid #1f2937", padding: "18px" }}>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Authorization Guard</span>
          <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#c084fc", marginTop: "4px" }}>
            Object-Level RBAC
          </div>
          <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Issuer-matched & Admin scoped</span>
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
          Authoritative Credential Status Table
        </h3>

        {credentials.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px", color: "#94a3b8", fontSize: "0.85rem" }}>
            No credentials found in authoritative registry.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>
                  <th style={{ padding: "10px 12px" }}>Credential ID</th>
                  <th style={{ padding: "10px 12px" }}>Status Index</th>
                  <th style={{ padding: "10px 12px" }}>Title / Type</th>
                  <th style={{ padding: "10px 12px" }}>Subject</th>
                  <th style={{ padding: "10px 12px" }}>Issuer</th>
                  <th style={{ padding: "10px 12px" }}>Issued / Expiry</th>
                  <th style={{ padding: "10px 12px" }}>Status</th>
                  <th style={{ padding: "10px 12px" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map((c) => (
                  <tr key={c.id} style={{ borderBottom: "1px solid #1f2937" }}>
                    <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#94a3b8", fontSize: "0.75rem" }} title={c.id}>
                      {c.id.length > 20 ? `${c.id.substring(0, 18)}...` : c.id}
                    </td>
                    <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>
                      {c.status_list_index !== undefined && c.status_list_index !== null
                        ? `#${c.status_list_index}`
                        : "—"}
                    </td>
                    <td style={{ padding: "12px", fontWeight: 600, color: "#f8fafc" }}>
                      {c.title}
                    </td>
                    <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#94a3b8" }} title={c.user_did || c.wallet_address}>
                      {c.user_did
                        ? (c.user_did.length > 18 ? `${c.user_did.slice(0, 16)}...` : c.user_did)
                        : (c.wallet_address ? `${c.wallet_address.slice(0, 10)}...` : "—")}
                    </td>
                    <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#94a3b8" }} title={c.issuer}>
                      {c.issuer_name || (c.issuer.length > 18 ? `${c.issuer.slice(0, 16)}...` : c.issuer)}
                    </td>
                    <td style={{ padding: "12px", color: "#94a3b8", fontSize: "0.75rem" }}>
                      {c.issued_date || "—"} / {c.expiry_date || "Permanent"}
                    </td>
                    <td style={{ padding: "12px" }}>
                      <StatusChip status={c.status} size="sm" />
                    </td>
                    <td style={{ padding: "12px" }}>
                      {c.status === "ACTIVE" ? (
                        <button
                          onClick={() => openRevokeModal(c)}
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
                          Revoke
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
        )}
      </div>

      {/* Revocation Confirmation Modal */}
      {selectedCred && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "20px"
          }}
        >
          <div
            style={{
              backgroundColor: "#111827",
              border: "1px solid #374151",
              borderRadius: "16px",
              padding: "24px",
              maxWidth: "520px",
              width: "100%",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)"
            }}
          >
            {/* Modal Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <AlertTriangle size={22} color="#f87171" />
                <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 700, color: "#ffffff" }}>
                  Confirm Credential Revocation
                </h3>
              </div>
              <button
                onClick={closeRevokeModal}
                disabled={isSubmitting}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer"
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Details */}
            <div style={{ fontSize: "0.85rem", color: "#cbd5e1", lineHeight: 1.5 }}>
              <p style={{ margin: "0 0 12px 0" }}>
                You are about to permanently revoke this credential. This action is <strong>irreversible</strong> and will update the authoritative Bitstring Status List.
              </p>
              <div style={{ backgroundColor: "#1f2937", padding: "12px", borderRadius: "8px", display: "flex", flexDirection: "column", gap: "6px" }}>
                <div><span style={{ color: "#94a3b8" }}>Title:</span> <strong style={{ color: "#ffffff" }}>{selectedCred.title}</strong></div>
                <div><span style={{ color: "#94a3b8" }}>Credential ID:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#cbd5e1" }}>{selectedCred.id}</span></div>
                <div><span style={{ color: "#94a3b8" }}>Status Index:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{selectedCred.status_list_index ?? "—"}</span></div>
                <div><span style={{ color: "#94a3b8" }}>Subject:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#cbd5e1" }}>{selectedCred.user_did || selectedCred.wallet_address}</span></div>
              </div>
            </div>

            {/* Modal Error Banner */}
            {modalError && (
              <div style={{
                padding: "10px 14px",
                backgroundColor: "rgba(239, 68, 68, 0.2)",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                borderRadius: "8px",
                color: "#fca5a5",
                fontSize: "0.82rem"
              }}>
                {modalError}
              </div>
            )}

            {/* Revocation Reason Selection */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "#e2e8f0" }}>
                Revocation Reason (Mandatory for Audit Trail)
              </label>
              <select
                value={revocationReason}
                onChange={(e) => setRevocationReason(e.target.value)}
                disabled={isSubmitting}
                style={{
                  padding: "10px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  outline: "none"
                }}
              >
                <option value="AFFILIATION_TERMINATED">Affiliation Terminated / Completed</option>
                <option value="KEY_COMPROMISE">Key Compromise / Security Incident</option>
                <option value="ISSUANCE_ERROR">Issuance Error / Administrative Correction</option>
                <option value="PRIVILEGE_WITHDRAWN">Privilege Withdrawn</option>
                <option value="CUSTOM">Other (Specify below)</option>
              </select>

              {revocationReason === "CUSTOM" && (
                <input
                  type="text"
                  placeholder="Enter detailed revocation justification..."
                  value={customReason}
                  onChange={(e) => setCustomReason(e.target.value)}
                  disabled={isSubmitting}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "8px",
                    backgroundColor: "#1f2937",
                    border: "1px solid #374151",
                    color: "#ffffff",
                    fontSize: "0.85rem",
                    outline: "none",
                    marginTop: "6px"
                  }}
                />
              )}
            </div>

            {/* Modal Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
              <button
                onClick={closeRevokeModal}
                disabled={isSubmitting}
                style={{
                  padding: "8px 16px",
                  borderRadius: "8px",
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  color: "#e2e8f0",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRevoke}
                disabled={isSubmitting}
                style={{
                  padding: "8px 20px",
                  borderRadius: "8px",
                  backgroundColor: "#dc2626",
                  border: "none",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  fontWeight: 700,
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  opacity: isSubmitting ? 0.7 : 1
                }}
              >
                {isSubmitting ? "Revoking..." : "Confirm Revocation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
