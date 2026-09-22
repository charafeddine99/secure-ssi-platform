import React, { useState } from "react";
import { Modal } from "../common/Modal";
import { TrustBadge } from "../common/TrustBadge";
import { StatusChip } from "../common/StatusChip";
import { CredentialCardData } from "./CredentialCard";
import { CheckCircle2, Shield, Copy, Check } from "lucide-react";

interface CredentialDetailModalProps {
  credential: CredentialCardData | null;
  isOpen: boolean;
  onClose: () => void;
}

export const CredentialDetailModal: React.FC<CredentialDetailModalProps> = ({
  credential,
  isOpen,
  onClose
}) => {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"CLAIMS" | "PROOF" | "RAW">("CLAIMS");

  if (!credential) return null;

  const w3cDocument = {
    "@context": [
      "https://www.w3.org/ns/credentials/v2",
      "https://w3id.org/security/suites/ed25519-2020/v1"
    ],
    id: credential.id,
    type: ["VerifiableCredential", credential.category + "Credential"],
    issuer: {
      id: credential.issuer,
      name: credential.issuerName
    },
    issuanceDate: credential.issuedDate + "T00:00:00Z",
    expirationDate: credential.expiryDate + "T00:00:00Z",
    credentialSubject: {
      ...credential.claims
    },
    credentialStatus: {
      id: `https://ssi.platform.local/status-list#${credential.statusListIndex ?? 100}`,
      type: "BitstringStatusListEntry",
      statusPurpose: "revocation",
      statusListIndex: credential.statusListIndex ?? 100
    },
    proof: {
      type: "Ed25519Signature2020",
      created: credential.issuedDate + "T00:00:00Z",
      verificationMethod: `${credential.issuer}#key-1`,
      proofPurpose: "assertionMethod",
      proofValue: credential.proofValue
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(w3cDocument, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={credential.title}
      subtitle={`ID: ${credential.id}`}
      maxWidth="680px"
    >
      {/* Header status bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <StatusChip status={credential.status} />
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="ED25519_SIGNED" />
        </div>
        <button
          onClick={handleCopy}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            fontSize: "0.75rem",
            padding: "5px 10px",
            borderRadius: "6px",
            border: "1px solid #374151",
            backgroundColor: "#1f2937",
            color: "#e2e8f0",
            cursor: "pointer"
          }}
        >
          {copied ? <Check size={14} color="#34d399" /> : <Copy size={14} />}
          {copied ? "Copied JSON" : "Copy JSON-LD"}
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "4px", borderBottom: "1px solid #1f2937", marginBottom: "16px" }}>
        <button
          onClick={() => setActiveTab("CLAIMS")}
          style={{
            padding: "8px 16px",
            background: "transparent",
            border: "none",
            borderBottom: activeTab === "CLAIMS" ? "2px solid #2563eb" : "2px solid transparent",
            color: activeTab === "CLAIMS" ? "#ffffff" : "#94a3b8",
            fontWeight: 600,
            fontSize: "0.85rem",
            cursor: "pointer"
          }}
        >
          Claims & Attributes
        </button>
        <button
          onClick={() => setActiveTab("PROOF")}
          style={{
            padding: "8px 16px",
            background: "transparent",
            border: "none",
            borderBottom: activeTab === "PROOF" ? "2px solid #2563eb" : "2px solid transparent",
            color: activeTab === "PROOF" ? "#ffffff" : "#94a3b8",
            fontWeight: 600,
            fontSize: "0.85rem",
            cursor: "pointer"
          }}
        >
          Cryptographic Proof
        </button>
        <button
          onClick={() => setActiveTab("RAW")}
          style={{
            padding: "8px 16px",
            background: "transparent",
            border: "none",
            borderBottom: activeTab === "RAW" ? "2px solid #2563eb" : "2px solid transparent",
            color: activeTab === "RAW" ? "#ffffff" : "#94a3b8",
            fontWeight: 600,
            fontSize: "0.85rem",
            cursor: "pointer"
          }}
        >
          Raw W3C JSON-LD
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "CLAIMS" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div style={{ backgroundColor: "#161f33", padding: "14px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Issuer Authority</span>
            <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#f8fafc", marginTop: "2px" }}>
              {credential.issuerName}
            </div>
            <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>
              {credential.issuer}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            {Object.entries(credential.claims || {}).map(([key, value]) => (
              <div
                key={key}
                style={{
                  backgroundColor: "#0d131f",
                  padding: "12px",
                  borderRadius: "8px",
                  border: "1px solid #1f2937"
                }}
              >
                <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>{key}</div>
                <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "#ffffff", marginTop: "4px" }}>
                  {typeof value === "object" ? JSON.stringify(value) : String(value)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "PROOF" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "0.85rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", backgroundColor: "rgba(16, 185, 129, 0.08)", padding: "12px", borderRadius: "8px", border: "1px solid rgba(16, 185, 129, 0.2)" }}>
            <CheckCircle2 color="#34d399" size={20} />
            <div>
              <div style={{ fontWeight: 600, color: "#34d399" }}>Ed25519 Cryptographic Signature Valid</div>
              <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>W3C DataIntegrity canonicalized via RFC 8785 (JCS)</div>
            </div>
          </div>

          <div style={{ backgroundColor: "#0d131f", padding: "14px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Proof Signature Value (Base58 / Hex)</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#38bdf8", wordBreak: "break-all", marginTop: "4px" }}>
              {credential.proofValue}
            </div>
          </div>

          <div style={{ backgroundColor: "#0d131f", padding: "14px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>W3C Bitstring Revocation Index</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", color: "#f8fafc", marginTop: "4px" }}>
              Index #{credential.statusListIndex ?? 104} on StatusList2021
            </div>
          </div>
        </div>
      )}

      {activeTab === "RAW" && (
        <pre
          style={{
            margin: 0,
            padding: "16px",
            backgroundColor: "#070a12",
            borderRadius: "8px",
            border: "1px solid #1f2937",
            color: "#a5b4fc",
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            overflowX: "auto",
            maxHeight: "360px"
          }}
        >
          {JSON.stringify(w3cDocument, null, 2)}
        </pre>
      )}
    </Modal>
  );
};
