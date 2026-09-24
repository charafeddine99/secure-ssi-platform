import React from "react";
import { CheckCircle2, XCircle, ShieldCheck, ShieldAlert, Cpu, Link, Lock, UserCheck, Calendar, FileCheck } from "lucide-react";
import { NinePointVerificationResult } from "../../services/api";

interface NinePointVerificationMatrixProps {
  result: NinePointVerificationResult;
  disclosedClaims?: Record<string, any>;
  aiRiskScore?: number;
  nonce?: string;
  sessionId?: string;
}

export const NinePointVerificationMatrix: React.FC<NinePointVerificationMatrixProps> = ({
  result,
  disclosedClaims,
  aiRiskScore = 12,
  nonce,
  sessionId,
}) => {
  const isAccepted = result.finalPolicyResult === "ACCEPTED";

  const checklistItems = [
    {
      num: 1,
      title: "Credential Structure & Profile Integrity",
      desc: "Validates W3C VC 2.0 schema, canonical syntax, and context consistency.",
      valid: result.credentialValid,
      icon: <FileCheck size={16} />,
      detail: result.evaluations?.credential || "Valid W3C VC 2.0 profile format",
    },
    {
      num: 2,
      title: "Issuer Trust & DID Resolution",
      desc: "Resolves issuer DID and validates trust anchor accreditation.",
      valid: result.issuerTrusted,
      icon: <Lock size={16} />,
      detail: result.evaluations?.issuer || "Verified trusted issuer DID document",
    },
    {
      num: 3,
      title: "Ed25519 Cryptographic Signature",
      desc: "Verifies linked data signature using JCS RFC 8785 canonicalization.",
      valid: result.signatureValid,
      icon: <ShieldCheck size={16} />,
      detail: result.evaluations?.signature || "Cryptographic proof mathematically valid",
    },
    {
      num: 4,
      title: "Holder Binding & Subject Proof",
      desc: "Ensures credential holder matches subject and presentation signer DID.",
      valid: result.holderBindingValid,
      icon: <UserCheck size={16} />,
      detail: result.evaluations?.holder_binding || "Holder DID bound to presentation signature",
    },
    {
      num: 5,
      title: "Expiration & Temporal Validity Window",
      desc: "Confirms validFrom <= now <= validUntil with server clock synchronization.",
      valid: result.expirationValid,
      icon: <Calendar size={16} />,
      detail: result.evaluations?.expiration || "Within active validity window",
    },
    {
      num: 6,
      title: "Bitstring Revocation Status List",
      desc: "Verifies revocation slot in W3C Bitstring Status List.",
      valid: result.revocationStatusClear,
      icon: <CheckCircle2 size={16} />,
      detail: result.evaluations?.revocation || "Status slot is active (unrevoked)",
    },
    {
      num: 7,
      title: "Nonce & Freshness Challenge",
      desc: "Protects against replay attacks by binding presentation to session challenge.",
      valid: result.challengeValid,
      icon: <Lock size={16} />,
      detail: nonce ? `Nonce verified: ${nonce.substring(0, 16)}...` : (result.evaluations?.challenge || "Nonce match confirmed"),
    },
    {
      num: 8,
      title: "AI Behavioral Risk & Threat Evaluation",
      desc: "Analyzes presentation patterns using Autoencoder & XGBoost risk engine.",
      valid: result.aiRiskLevel !== "HIGH",
      icon: <Cpu size={16} />,
      detail: `Risk Level: ${result.aiRiskLevel} (Score: ${aiRiskScore}/100)`,
    },
    {
      num: 9,
      title: "Blockchain Anchor & Timestamp Proof",
      desc: "Verifies immutable on-chain status registry state reference.",
      valid: result.blockchainAnchored,
      icon: <Link size={16} />,
      detail: result.evaluations?.blockchain || "Anchored on local Hardhat Ethereum node",
    },
  ];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "18px",
        backgroundColor: "#0d131f",
        border: `1px solid ${isAccepted ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)"}`,
        borderRadius: "16px",
        padding: "24px",
      }}
    >
      {/* Header Banner */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingBottom: "16px",
          borderBottom: "1px solid #1f2937",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {isAccepted ? (
            <div style={{ padding: "10px", borderRadius: "12px", background: "rgba(16, 185, 129, 0.15)", color: "#34d399" }}>
              <ShieldCheck size={28} />
            </div>
          ) : (
            <div style={{ padding: "10px", borderRadius: "12px", background: "rgba(239, 68, 68, 0.15)", color: "#f87171" }}>
              <ShieldAlert size={28} />
            </div>
          )}
          <div>
            <h3 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700, color: "#ffffff" }}>
              Master 9-Point Verification Matrix
            </h3>
            <p style={{ margin: "2px 0 0 0", fontSize: "0.8rem", color: "#94a3b8" }}>
              Standards-aligned OID4VP Direct Post Verification Engine
            </p>
          </div>
        </div>

        {/* Policy Result Badge */}
        <div
          style={{
            padding: "8px 18px",
            borderRadius: "9999px",
            fontSize: "0.85rem",
            fontWeight: 800,
            letterSpacing: "0.05em",
            backgroundColor: isAccepted ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
            color: isAccepted ? "#34d399" : "#f87171",
            border: `1px solid ${isAccepted ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)"}`,
          }}
        >
          {result.finalPolicyResult}
        </div>
      </div>

      {sessionId && (
        <div style={{ fontSize: "0.75rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
          Session ID: {sessionId}
        </div>
      )}

      {/* 9-Point Verification Rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {checklistItems.map((item) => (
          <div
            key={item.num}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              backgroundColor: "rgba(15, 23, 42, 0.6)",
              borderRadius: "10px",
              border: `1px solid ${item.valid ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.2)"}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ color: item.valid ? "#34d399" : "#f87171" }}>
                {item.valid ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
              </div>
              <div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc" }}>
                  {item.num}. {item.title}
                </div>
                <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                  {item.desc}
                </div>
              </div>
            </div>

            <div
              style={{
                fontSize: "0.75rem",
                fontFamily: "var(--font-mono)",
                color: item.valid ? "#38bdf8" : "#f87171",
                maxWidth: "260px",
                textAlign: "right",
              }}
            >
              {item.detail}
            </div>
          </div>
        ))}
      </div>

      {/* Disclosed Claims Section */}
      {disclosedClaims && Object.keys(disclosedClaims).length > 0 && (
        <div
          style={{
            marginTop: "10px",
            backgroundColor: "#111827",
            borderRadius: "12px",
            padding: "14px",
            border: "1px solid #1f2937",
          }}
        >
          <h4 style={{ margin: "0 0 10px 0", fontSize: "0.9rem", color: "#ffffff", fontWeight: 600 }}>
            Selectively Disclosed Attributes (Consent Sheet Cleared)
          </h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px" }}>
            {Object.entries(disclosedClaims).map(([k, v]) => (
              <div
                key={k}
                style={{
                  padding: "8px 12px",
                  backgroundColor: "rgba(0, 0, 0, 0.3)",
                  borderRadius: "8px",
                  border: "1px solid rgba(148, 163, 184, 0.1)",
                }}
              >
                <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>{k}</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#60a5fa", marginTop: "2px" }}>
                  {String(v)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
