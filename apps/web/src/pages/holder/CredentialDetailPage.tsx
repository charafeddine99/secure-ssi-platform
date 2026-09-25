import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { ArrowLeft, CheckCircle2, Shield, Copy, Check, QrCode } from "lucide-react";

export const CredentialDetailPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  // Sample or loaded credential data
  const credential = {
    id: id || "urn:uuid:natid-prototype-2026-tr",
    title: "Standards-Aligned National Identity",
    category: "IDENTITY",
    issuer: "did:gov:eudi:nvi-authority",
    issuerName: "T.C. Nüfus ve Vatandaşlık İşleri (Prototype)",
    issuedDate: "2025-01-15",
    expiryDate: "2035-01-15",
    status: "ACTIVE" as const,
    claims: {
      "Full Name": "Charaf Eddine Bessanane",
      "Nationality": "TUR",
      "National ID No": "TR-10293847561",
      "Birth Date": "1999-04-12",
      "Birth Place": "Istanbul",
      "Assurance Level": "Prototype High LoA (ISO/IEC 29115)"
    },
    proofValue: "z3s9PqRtXvM8EUDINationalIdentityProof2026Ed25519Signature"
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(credential, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <span style={{ fontSize: "0.7rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase" }}>
              {credential.category} CREDENTIAL
            </span>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#ffffff", margin: "2px 0 0 0" }}>
              {credential.title}
            </h2>
          </div>
          <StatusChip status={credential.status} />
        </div>

        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
          <TrustBadge level="ED25519_SIGNED" size="sm" />
          <TrustBadge level="DEMO_TRUST_LEVEL" size="sm" />
        </div>

        {/* Claims Table */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <span style={{ fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Attested Claims:
          </span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "8px" }}>
            {Object.entries(credential.claims).map(([k, v]) => (
              <div
                key={k}
                style={{
                  backgroundColor: "#0d131f",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: "1px solid #1f2937",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center"
                }}
              >
                <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>{k}</span>
                <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc" }}>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Proof info */}
        <div style={{ backgroundColor: "#0d131f", padding: "12px", borderRadius: "8px", border: "1px solid #1f2937" }}>
          <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Ed25519 Linked Data Signature:</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#38bdf8", wordBreak: "break-all", marginTop: "4px" }}>
            {credential.proofValue}
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={handleCopy}
            style={{
              flex: 1,
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              color: "#e2e8f0",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            {copied ? <Check size={16} color="#34d399" /> : <Copy size={16} />}
            {copied ? "Copied JSON-LD" : "Copy W3C JSON-LD"}
          </button>

          <button
            onClick={() => navigate("/wallet/consent")}
            style={{
              flex: 1,
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              border: "none",
              color: "#ffffff",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            <QrCode size={16} />
            Present Credential
          </button>
        </div>
      </div>
    </div>
  );
};
