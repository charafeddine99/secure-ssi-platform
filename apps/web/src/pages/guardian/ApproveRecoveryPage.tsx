import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  fetchRecoveryRequestById,
  fetchGuardians,
  fetchCurrentUserId,
  approveRecoveryPetition,
  rejectRecoveryPetition,
  RecoveryRequest,
} from "../../services/api";
import {
  ShieldCheck,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from "lucide-react";

export const ApproveRecoveryPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [request, setRequest] = useState<RecoveryRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [signing, setSigning] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [guardianId, setGuardianId] = useState<string | null>(null);
  const [guardianDid, setGuardianDid] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadRequest = async () => {
      setLoading(true);
      try {
        if (!id) throw new Error("Recovery request ID is missing.");
        const found = await fetchRecoveryRequestById(id);
        if (!found) throw new Error("Recovery request was not found for this account.");
        setRequest(found);
        const [userId, guardians] = await Promise.all([
          fetchCurrentUserId(),
          fetchGuardians(found.walletId),
        ]);
        const assignment = guardians.find(
          (guardian) => guardian.guardian_user_id === userId && guardian.approved === 1
        );
        setGuardianId(assignment?.guardian_id || null);
        setGuardianDid(assignment?.guardian_did || null);
        if (!assignment) setError("This signed-in account has no active Guardian assignment for the request.");
      } catch (loadError: unknown) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load petition and Guardian assignment.");
      } finally {
        setLoading(false);
      }
    };
    loadRequest();
  }, [id]);

  const handleApprove = async () => {
    if (!request || !guardianId || !guardianDid || !request.challenge || request.status !== "PENDING_APPROVALS") {
      setError("An active request, assigned Guardian DID, and current server challenge are required.");
      return;
    }
    setSigning(true);
    setError(null);
    try {
      const result = await approveRecoveryPetition(request, guardianId, guardianDid);
      setRequest(result.recovery);
      setSuccessMsg(`Guardian account decision recorded. Current state: ${result.recovery.status}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to submit guardian approval.");
    } finally {
      setSigning(false);
    }
  };

  const handleReject = async () => {
    if (!request || !guardianId || !guardianDid || !request.challenge || request.status !== "PENDING_APPROVALS") {
      setError("An active request, assigned Guardian DID, and current server challenge are required.");
      return;
    }
    setRejecting(true);
    setError(null);
    try {
      const result = await rejectRecoveryPetition(request, guardianId, guardianDid);
      setRequest(result.recovery);
      setSuccessMsg(`Guardian rejection recorded. Current state: ${result.recovery.status}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reject petition.");
    } finally {
      setRejecting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "780px" }}>
      <button
        onClick={() => navigate("/guardian")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          backgroundColor: "transparent",
          border: "none",
          color: "#94a3b8",
          fontSize: "0.85rem",
          cursor: "pointer",
          padding: 0,
        }}
      >
        <ArrowLeft size={16} />
        Back to Guardian Network
      </button>

      <div>
        <p className="workspace-eyebrow">Recovery approval</p>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Guardian Recovery Decision
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Review the request and submit a decision using the assigned Guardian account.
        </p>
      </div>

      {error && (
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
          {error}
        </div>
      )}

      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
        }}
      >
        {successMsg ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#34d399" }}>
              <CheckCircle2 size={28} />
              <div>
                <h3 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                  {successMsg}
                </h3>
                <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "2px 0 0 0" }}>
                  The Recovery Service verifies a short-lived signature from the registered Guardian DID. The Identity Service performs signing with a server-managed key; this does not establish device-held key custody or an on-chain receipt.
                </p>
              </div>
            </div>

            <button
              onClick={() => navigate("/guardian/requests")}
              style={{
                padding: "10px 18px",
                borderRadius: "8px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                fontSize: "0.85rem",
                fontWeight: 600,
                cursor: "pointer",
                alignSelf: "flex-start",
              }}
            >
              Return to Recovery Petitions
            </button>
          </div>
        ) : loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#94a3b8", padding: "20px" }}>
            <RefreshCw size={16} className="animate-spin" />
            Loading petition details...
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.78rem", fontFamily: "var(--font-mono)", color: "#fbbf24" }}>
                Petition ID: {request?.requestId || id}
              </span>
              <span style={{ fontSize: "0.75rem", padding: "4px 10px", borderRadius: "9999px", backgroundColor: "rgba(59, 130, 246, 0.2)", color: "#60a5fa", fontWeight: 700 }}>
                STATUS: {request?.status || "UNKNOWN"}
              </span>
            </div>

            <div style={{ backgroundColor: "#0d131f", padding: "16px", borderRadius: "10px", border: "1px solid #1f2937", display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.85rem" }}>
              <div>
                <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Target Sovereign Wallet:</span>
                <div style={{ fontFamily: "var(--font-mono)", color: "#f87171", marginTop: "2px" }}>
                  {request?.walletId || "Unavailable"}
                </div>
              </div>

              <div>
                <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Stated Reason for Emergency Recovery:</span>
                <div style={{ color: "#ffffff", marginTop: "2px", lineHeight: "1.4" }}>
                  {request?.reason || "Reason not supplied"}
                </div>
              </div>

              <div>
                <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Quorum Progress:</span>
                <div style={{ color: "#fbbf24", fontWeight: 700, marginTop: "2px" }}>
                  {request?.approvalsCount ?? "Unknown"} of {request?.requiredCount ?? "Unknown"} approvals recorded
                </div>
              </div>
            </div>

            <div
              style={{
                backgroundColor: "rgba(245, 158, 11, 0.1)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                padding: "12px 14px",
                borderRadius: "8px",
                fontSize: "0.8rem",
                color: "#fbbf24",
                lineHeight: "1.4",
              }}
            >
              <strong>Signing boundary:</strong> The Identity Service signs this decision with a server-managed key. This account does not hold an independent Guardian signing key.
            </div>

            <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
              <button
                onClick={handleApprove}
                disabled={signing || rejecting || !guardianId || !guardianDid || !request?.challenge || request?.status !== "PENDING_APPROVALS"}
                style={{
                  flex: 1,
                  padding: "12px",
                  borderRadius: "10px",
                  backgroundColor: "#059669",
                  color: "#ffffff",
                  fontSize: "0.9rem",
                  fontWeight: 700,
                  border: "none",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                }}
              >
                {signing ? (
                  <span>Submitting decision...</span>
                ) : (
                  <>
                    <ShieldCheck size={18} />
                    Approve Request
                  </>
                )}
              </button>

              <button
                onClick={handleReject}
                disabled={signing || rejecting || !guardianId || !guardianDid || !request?.challenge || request?.status !== "PENDING_APPROVALS"}
                style={{
                  padding: "12px 20px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(239, 68, 68, 0.15)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  color: "#f87171",
                  fontSize: "0.9rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <XCircle size={16} />
                Decline / Oppose
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
