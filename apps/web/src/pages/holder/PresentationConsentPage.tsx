import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { ShieldCheck, Lock, Eye, EyeOff, CheckCircle2, ArrowLeft, Send } from "lucide-react";

export const PresentationConsentPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const verifierInfo = {
    name: "European Border Control & E-Gates (Prototype)",
    purpose: "Border clearance age condition (Over 18) and nationality validation.",
    requiredClaims: ["Nationality", "Uyruk"],
    predicateDescription: "Zero-knowledge condition proof: Age >= 18 without revealing Date of Birth."
  };

  const credentialClaims: Record<string, any> = {
    "Full Name": "Charaf Eddine Bessanane",
    "Nationality": "TUR",
    "National ID No": "TR-10293847561",
    "Birth Date": "1999-04-12",
    "Document Serial": "A92K81029",
    "Assurance Level": "Prototype High LoA"
  };

  // State: selected claims to reveal
  const [selectedClaims, setSelectedClaims] = useState<Record<string, boolean>>({
    "Nationality": true,
    "Full Name": false,
    "National ID No": false,
    "Birth Date": false,
    "Document Serial": false,
    "Assurance Level": true
  });

  const [shareOver18Proof, setShareOver18Proof] = useState<boolean>(true);
  const [presenting, setPresenting] = useState(false);
  const [success, setSuccess] = useState(false);

  const toggleClaim = (key: string) => {
    setSelectedClaims((prev) => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const handleApprove = () => {
    setPresenting(true);
    setTimeout(() => {
      setPresenting(false);
      setSuccess(true);
      setTimeout(() => {
        navigate("/wallet/activity");
      }, 1500);
    }, 1000);
  };

  const revealedCount = Object.values(selectedClaims).filter(Boolean).length;
  const hiddenCount = Object.keys(selectedClaims).length - revealedCount;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <button
        onClick={() => navigate("/wallet")}
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
        Back to Wallet
      </button>

      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "16px"
        }}
      >
        <div>
          <div style={{ display: "flex", gap: "6px", alignItems: "center", marginBottom: "8px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
            <TrustBadge level="DEMO_TRUST_LEVEL" size="sm" />
          </div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Selective Disclosure & Holder Consent
          </h2>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Granular data minimization compliant with W3C VC 2.0 & EUDI ARF draft specifications.
          </p>
        </div>

        {/* Verifier Card */}
        <div
          style={{
            backgroundColor: "#0d131f",
            borderRadius: "10px",
            border: "1px solid #1f2937",
            padding: "14px"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#60a5fa", fontSize: "0.85rem", fontWeight: 600 }}>
            <Lock size={16} />
            <span>{verifierInfo.name}</span>
          </div>
          <div style={{ fontSize: "0.78rem", color: "#cbd5e1", marginTop: "4px" }}>
            {verifierInfo.purpose}
          </div>
        </div>

        {/* Predicate Proof Box (Over 18) */}
        <div
          style={{
            backgroundColor: "rgba(16, 185, 129, 0.08)",
            borderRadius: "10px",
            border: "1px solid rgba(16, 185, 129, 0.25)",
            padding: "12px 14px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}
        >
          <div>
            <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "#34d399" }}>
              Age Verification Predicate Proof
            </div>
            <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "2px" }}>
              {verifierInfo.predicateDescription}
            </div>
          </div>
          <input
            type="checkbox"
            checked={shareOver18Proof}
            onChange={(e) => setShareOver18Proof(e.target.checked)}
            style={{ width: "18px", height: "18px", accentColor: "#10b981", cursor: "pointer" }}
          />
        </div>

        {/* Minimization Stats */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "0.78rem",
            padding: "8px 12px",
            backgroundColor: "#161f33",
            borderRadius: "8px",
            color: "#cbd5e1"
          }}
        >
          <span>
            Revealing: <strong style={{ color: "#60a5fa" }}>{revealedCount}</strong> claims
          </span>
          <span>
            Blinded: <strong style={{ color: "#f87171" }}>{hiddenCount}</strong> claims (Salted SHA-256)
          </span>
        </div>

        {/* Claims Checklist */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {Object.entries(credentialClaims).map(([key, value]) => {
            const isRevealed = !!selectedClaims[key];
            const isRequired = verifierInfo.requiredClaims.includes(key);

            return (
              <label
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  backgroundColor: isRevealed ? "rgba(37, 99, 235, 0.08)" : "#0d131f",
                  border: isRevealed ? "1px solid rgba(37, 99, 235, 0.35)" : "1px solid #1f2937",
                  cursor: "pointer"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <input
                    type="checkbox"
                    checked={isRevealed}
                    onChange={() => toggleClaim(key)}
                    style={{ width: "16px", height: "16px", accentColor: "#2563eb", cursor: "pointer" }}
                  />
                  <div>
                    <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#f8fafc" }}>
                      {key} {isRequired && <span style={{ color: "#fbbf24", fontSize: "0.68rem" }}>(Requested)</span>}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: isRevealed ? "#93c5fd" : "#64748b" }}>
                      {isRevealed ? String(value) : "Blinded with Salted Commitment"}
                    </div>
                  </div>
                </div>

                <div>
                  {isRevealed ? <Eye size={16} color="#60a5fa" /> : <EyeOff size={16} color="#64748b" />}
                </div>
              </label>
            );
          })}
        </div>

        {/* Submit */}
        <button
          onClick={handleApprove}
          disabled={presenting || success}
          style={{
            width: "100%",
            padding: "12px",
            borderRadius: "10px",
            backgroundColor: success ? "#10b981" : "#2563eb",
            color: "#ffffff",
            fontWeight: 700,
            fontSize: "0.9rem",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            marginTop: "8px"
          }}
        >
          {success ? (
            <>
              <CheckCircle2 size={18} />
              Presentation Approved & Transmitted!
            </>
          ) : presenting ? (
            <span>Signing Aries DIDComm Envelope...</span>
          ) : (
            <>
              <Send size={16} />
              Confirm & Present to Verifier
            </>
          )}
        </button>
      </div>
    </div>
  );
};
