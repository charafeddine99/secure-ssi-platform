import React, { useState } from "react";
import { Modal } from "../common/Modal";
import { StatusChip } from "../common/StatusChip";
import type { CredentialCardData } from "./CredentialCard";
import { ShieldAlert, Copy, Check } from "lucide-react";

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
      "https://www.w3.org/ns/credentials/v2"
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
      <div className="holder-credential-detail-modal">
      {/* Header status bar */}
      <div className="holder-detail-toolbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <StatusChip status={credential.status} />
        </div>
        <button
          type="button"
          className="holder-secondary-action"
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
          {copied ? "Copied preview" : "Copy display preview"}
        </button>
        <span className="holder-sr-only" aria-live="polite">{copied ? "Credential display preview copied." : ""}</span>
      </div>

      {/* Tabs */}
      <div className="holder-detail-tabs" role="group" aria-label="Credential detail sections" style={{ display: "flex", gap: "4px", borderBottom: "1px solid #1f2937", marginBottom: "16px" }}>
        <button
          type="button"
          aria-pressed={activeTab === "CLAIMS"}
          className={activeTab === "CLAIMS" ? "is-active" : undefined}
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
          type="button"
          aria-pressed={activeTab === "PROOF"}
          className={activeTab === "PROOF" ? "is-active" : undefined}
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
          type="button"
          aria-pressed={activeTab === "RAW"}
          className={activeTab === "RAW" ? "is-active" : undefined}
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
          JSON-LD Preview
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "CLAIMS" && (
        <div className="holder-detail-content" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div className="holder-detail-issuer" style={{ backgroundColor: "#161f33", padding: "14px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Issuer Authority</span>
            <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#f8fafc", marginTop: "2px" }}>
              {credential.issuerName}
            </div>
            <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>
              {credential.issuer}
            </div>
          </div>

          <div className="holder-detail-claims" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            {Object.entries(credential.claims || {}).length > 0 ? Object.entries(credential.claims || {}).map(([key, value]) => (
              <div
                key={key}
                className="holder-detail-claim"
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
            )) : <p className="holder-detail-empty">No claim fields were returned for this credential.</p>}
          </div>
        </div>
      )}

      {activeTab === "PROOF" && (
        <div className="holder-detail-content" style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "0.85rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", backgroundColor: "rgba(245, 158, 11, 0.08)", padding: "12px", borderRadius: "8px", border: "1px solid rgba(245, 158, 11, 0.2)" }}>
            <ShieldAlert color="#fbbf24" size={20} />
            <div>
              <div style={{ fontWeight: 600, color: "#fbbf24" }}>Proof verification not performed in this view</div>
              <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>The displayed proof value is not evidence of a valid signature.</div>
            </div>
          </div>

          <div className="holder-detail-proof" style={{ backgroundColor: "#0d131f", padding: "14px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.75rem" }}>Proof value supplied by the credential record</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#38bdf8", wordBreak: "break-all", marginTop: "4px" }}>
              {credential.proofValue || "No proof value supplied"}
            </div>
          </div>
        </div>
      )}

      {activeTab === "RAW" && (
        <>
        <div className="holder-detail-content">
        <p style={{ margin: "0 0 10px", color: "#fbbf24", fontSize: "0.78rem" }}>
          This display preview is assembled from wallet fields. It is not the original serialized credential and does not verify its proof.
        </p>
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
        </div>
        </>
      )}
      </div>
    </Modal>
  );
};
