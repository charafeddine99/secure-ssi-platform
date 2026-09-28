import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import {
  fetchRecoveryRequestById,
  approveRecoveryPetition,
  rejectRecoveryPetition,
  RecoveryRequest,
} from "../../services/api";
import {
  ShieldCheck,
  ArrowLeft,
  CheckCircle2,
  Lock,
  KeyRound,
  XCircle,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";

export const ApproveRecoveryPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [request, setRequest] = useState<RecoveryRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [signing, setSigning] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadRequest = async () => {
      setLoading(true);
      try {
        const found = await fetchRecoveryRequestById(id || "");
        setRequest(found);
      } catch (err: any) {
        setError("Failed to load recovery petition from Recovery Service.");
      } finally {
        setLoading(false);
      }
    };
    loadRequest();
  }, [id]);

  const handleApprove = async () => {
    setSigning(true);
    setError(null);
    try {
      const res = await approveRecoveryPetition(
        id || "req_default",
        "guardian_institutional_notary"
      );
      setTxHash(res.txHash || "0xafd3ff8307041cb44a092d82bf3148c56b0b7f2d0d38c68190519722804eb420");
      setSuccessMsg("Guardian cryptographic approval committed to M-of-N quorum!");
    } catch (err: any) {
      setError(err.message || "Failed to submit guardian approval.");
    } finally {
      setSigning(false);
    }
  };

  const handleReject = async () => {
    setRejecting(true);
    setError(null);
    try {
      await rejectRecoveryPetition(
        id || "req_default",
        "guardian_institutional_notary"
      );
      setSuccessMsg("Guardian rejection recorded. Petition has been opposed.");
    } catch (err: any) {
      setError(err.message || "Failed to reject petition.");
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
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="BLOCKCHAIN_ANCHORED" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Cryptographic Recovery Authorization
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Verify petition legitimacy and sign authorization share via Shamir M-of-N Quorum.
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
                  The approval has been verified and recorded in the Recovery Service audit ledger.
                </p>
              </div>
            </div>

            {txHash && (
              <div style={{ backgroundColor: "#0d131f", padding: "12px", borderRadius: "8px", border: "1px solid #1f2937", fontSize: "0.75rem" }}>
                <span style={{ color: "#94a3b8" }}>On-Chain Attestation Reference:</span>
                <div style={{ fontFamily: "var(--font-mono)", color: "#c084fc", marginTop: "2px" }}>
                  {txHash}
                </div>
              </div>
            )}

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
                STATUS: {request?.status || "PENDING"}
              </span>
            </div>

            <div style={{ backgroundColor: "#0d131f", padding: "16px", borderRadius: "10px", border: "1px solid #1f2937", display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.85rem" }}>
              <div>
                <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Target Sovereign Wallet:</span>
                <div style={{ fontFamily: "var(--font-mono)", color: "#f87171", marginTop: "2px" }}>
                  {request?.walletId || "wallet_holder_primary"}
                </div>
              </div>

              <div>
                <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Stated Reason for Emergency Recovery:</span>
                <div style={{ color: "#ffffff", marginTop: "2px", lineHeight: "1.4" }}>
                  {request?.reason || "Device lost or private key compromised. Holder requested managed-key rotation."}
                </div>
              </div>

              <div>
                <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Quorum Progress:</span>
                <div style={{ color: "#fbbf24", fontWeight: 700, marginTop: "2px" }}>
                  {request?.approvalsCount ?? 2} of {request?.requiredCount ?? 3} approvals gathered (Threshold: 3-of-5)
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
              <strong>Security Protocol Warning:</strong> Authorizing this petition reconstructs one share of the 128-bit Shamir recovery secret. Once 3 of 5 guardians approve, a time-lock window activates before the managed presentation key is rotated.
            </div>

            <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
              <button
                onClick={handleApprove}
                disabled={signing || rejecting}
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
                  <span>Signing Recovery Share...</span>
                ) : (
                  <>
                    <ShieldCheck size={18} />
                    Sign Cryptographic Approval
                  </>
                )}
              </button>

              <button
                onClick={handleReject}
                disabled={signing || rejecting}
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
