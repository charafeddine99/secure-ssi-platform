import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { RiskScorePanel } from "../../components/security/RiskScorePanel";
import { issueCredential, assessFraudRisk } from "../../services/api";
import { PlusCircle, ShieldCheck, ArrowLeft, CheckCircle2, AlertTriangle, Send } from "lucide-react";

export const IssueCredentialPage: React.FC = () => {
  const navigate = useNavigate();

  const [category, setCategory] = useState<string>("IDENTITY");
  const [title, setTitle] = useState("Standards-Aligned National Identity Card");
  const [recipientWallet, setRecipientWallet] = useState("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266");
  const [recipientDid, setRecipientDid] = useState("did:key:z6MkuBesnaSecureHolder2026Ed25519");
  const [subjectName, setSubjectName] = useState("Charaf Eddine Bessanane");
  const [nationalId, setNationalId] = useState("TR-10293847561");
  const [nationality, setNationality] = useState("TUR");
  const [birthDate, setBirthDate] = useState("1999-04-12");

  const [assessingRisk, setAssessingRisk] = useState(false);
  const [riskAssessment, setRiskAssessment] = useState<any>(null);
  const [issuing, setIssuing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Evaluate risk via AI threat engine
  const handleAssessRisk = async () => {
    setAssessingRisk(true);
    setError(null);
    try {
      const assessment = await assessFraudRisk({
        wallet_address: recipientWallet,
        did_id: recipientDid,
        ip_address: "127.0.0.1",
        device_fingerprint: "device-sec-vault-browser-2026",
        recent_failed_attempts: 0
      });
      setRiskAssessment(assessment);
    } catch (err: any) {
      setError("AI assessment failed or service unreachable: " + err.message);
    } finally {
      setAssessingRisk(false);
    }
  };

  // Submit issuance
  const handleIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    setIssuing(true);
    setError(null);

    const claims: Record<string, any> = {
      "Full Name": subjectName,
      "Nationality": nationality,
      "National ID No": nationalId,
      "Birth Date": birthDate,
      "Assurance Level": "Prototype High LoA"
    };

    try {
      const res = await issueCredential({
        wallet_address: recipientWallet,
        did_id: recipientDid,
        credential_type: category + "Credential",
        title,
        category,
        claims
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Credential issuance failed.");
    } finally {
      setIssuing(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "880px" }}>
      <button
        onClick={() => navigate("/issuer")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          backgroundColor: "transparent",
          border: "none",
          color: "#94a3b8",
          fontSize: "0.85rem",
          cursor: "pointer",
          padding: 0
        }}
      >
        <ArrowLeft size={16} />
        Back to Dashboard
      </button>

      <div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Issue Verifiable Credential
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          W3C VC 2.0 issuance wizard with pre-issuance AI risk verification and EVM anchoring.
        </p>
      </div>

      {result ? (
        <div
          style={{
            backgroundColor: "#111827",
            borderRadius: "16px",
            border: "1px solid rgba(16, 185, 129, 0.4)",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "16px"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#34d399" }}>
            <CheckCircle2 size={28} />
            <div>
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                Credential Issued & Anchored!
              </h3>
              <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "2px 0 0 0" }}>
                Ed25519 linked data signature generated and Bitstring revocation slot allocated.
              </p>
            </div>
          </div>

          <div style={{ backgroundColor: "#0d131f", padding: "14px", borderRadius: "10px", border: "1px solid #1f2937", fontSize: "0.8rem" }}>
            <div style={{ color: "#94a3b8" }}>Credential URN:</div>
            <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>
              {result.credential_id || result.id || "urn:uuid:credential-success"}
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => {
                setResult(null);
                setRiskAssessment(null);
              }}
              style={{
                padding: "10px 18px",
                borderRadius: "8px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                fontWeight: 700,
                border: "none",
                cursor: "pointer"
              }}
            >
              Issue Another Credential
            </button>
            <button
              onClick={() => navigate("/issuer")}
              style={{
                padding: "10px 18px",
                borderRadius: "8px",
                backgroundColor: "#1f2937",
                color: "#e2e8f0",
                border: "1px solid #374151",
                cursor: "pointer"
              }}
            >
              Return to Console
            </button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={handleIssue}
          style={{
            backgroundColor: "#111827",
            borderRadius: "16px",
            border: "1px solid #1f2937",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "18px"
          }}
        >
          {error && (
            <div style={{ padding: "12px", borderRadius: "8px", backgroundColor: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#f87171", fontSize: "0.85rem" }}>
              {error}
            </div>
          )}

          {/* Credential Metadata */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Credential Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
              >
                <option value="IDENTITY">National Identity</option>
                <option value="QUALIFIED">Higher Education Attestation</option>
                <option value="FINANCE">Financial KYC Attestation</option>
                <option value="HEALTH">Health & Medical Record</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Display Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
              />
            </div>
          </div>

          {/* Recipient Subject */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Recipient EVM Address
              </label>
              <input
                type="text"
                value={recipientWallet}
                onChange={(e) => setRecipientWallet(e.target.value)}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Recipient Subject DID
              </label>
              <input
                type="text"
                value={recipientDid}
                onChange={(e) => setRecipientDid(e.target.value)}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
              />
            </div>
          </div>

          {/* Subject Claims */}
          <div style={{ borderTop: "1px solid #1f2937", paddingTop: "14px" }}>
            <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc", display: "block", marginBottom: "10px" }}>
              Attested Subject Claims
            </span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>Full Name</label>
                <input
                  type="text"
                  value={subjectName}
                  onChange={(e) => setSubjectName(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>National ID No</label>
                <input
                  type="text"
                  value={nationalId}
                  onChange={(e) => setNationalId(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>Nationality</label>
                <input
                  type="text"
                  value={nationality}
                  onChange={(e) => setNationality(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>Birth Date</label>
                <input
                  type="date"
                  value={birthDate}
                  onChange={(e) => setBirthDate(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                />
              </div>
            </div>
          </div>

          {/* AI Pre-Issuance Threat Check Button & Results */}
          <div style={{ borderTop: "1px solid #1f2937", paddingTop: "14px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>
                AI Threat Assessment Gate
              </span>
              <button
                type="button"
                onClick={handleAssessRisk}
                disabled={assessingRisk}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  color: "#60a5fa",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                {assessingRisk ? "Evaluating AI Model..." : "Run Pre-Issuance AI Check"}
              </button>
            </div>

            {riskAssessment && (
              <RiskScorePanel
                score={riskAssessment.risk_score}
                isFraudulent={riskAssessment.is_fraudulent}
                xgboostProbability={riskAssessment.xgboost_probability}
                reconstructionMse={riskAssessment.reconstruction_mse}
                reasons={riskAssessment.reasons}
              />
            )}
          </div>

          {/* Submit Action */}
          <button
            type="submit"
            disabled={issuing}
            style={{
              width: "100%",
              padding: "12px",
              borderRadius: "10px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.95rem",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              marginTop: "8px"
            }}
          >
            {issuing ? (
              <span>Signing with Ed25519 & Anchoring...</span>
            ) : (
              <>
                <Send size={16} />
                Sign and Issue Verifiable Credential
              </>
            )}
          </button>
        </form>
      )}
    </div>
  );
};
