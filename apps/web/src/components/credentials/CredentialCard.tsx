import React from "react";
import { ShieldCheck, Eye, KeyRound, QrCode } from "lucide-react";
import { TrustBadge } from "../common/TrustBadge";
import { StatusChip } from "../common/StatusChip";

export interface CredentialCardData {
  id: string;
  title: string;
  category: string;
  issuerName: string;
  issuer: string;
  issuedDate: string;
  expiryDate: string;
  status: "ACTIVE" | "REVOKED";
  claims: Record<string, any>;
  proofValue: string;
  aiRiskScore?: number;
  statusListIndex?: number;
}

interface CredentialCardProps {
  credential: CredentialCardData;
  onViewDetails?: (cred: CredentialCardData) => void;
  onPresent?: (cred: CredentialCardData) => void;
}

export const CredentialCard: React.FC<CredentialCardProps> = ({
  credential,
  onViewDetails,
  onPresent
}) => {
  // Category styling gradients
  const getCategoryGradient = (cat: string) => {
    switch (cat.toUpperCase()) {
      case "IDENTITY":
        return "linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%)";
      case "QUALIFIED":
        return "linear-gradient(135deg, #312e81 0%, #111827 100%)";
      case "FINANCE":
        return "linear-gradient(135deg, #064e3b 0%, #0f172a 100%)";
      case "TRAVEL":
        return "linear-gradient(135deg, #701a75 0%, #0f172a 100%)";
      case "TRANSPORT":
        return "linear-gradient(135deg, #7c2d12 0%, #0f172a 100%)";
      case "HEALTH":
        return "linear-gradient(135deg, #134e4a 0%, #0f172a 100%)";
      default:
        return "linear-gradient(135deg, #1f2937 0%, #111827 100%)";
    }
  };

  const claimEntries = Object.entries(credential.claims || {}).slice(0, 3);

  return (
    <div
      style={{
        position: "relative",
        borderRadius: "16px",
        background: getCategoryGradient(credential.category),
        border: "1px solid rgba(255, 255, 255, 0.1)",
        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.15)",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        minHeight: "220px",
        transition: "transform 0.2s ease, box-shadow 0.2s ease",
        overflow: "hidden"
      }}
      className="credential-card-hover"
    >
      {/* Decorative Card Chip */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* SIM/Chip visual */}
          <div
            style={{
              width: "36px",
              height: "28px",
              borderRadius: "5px",
              background: "linear-gradient(135deg, #d97706 0%, #fbbf24 50%, #b45309 100%)",
              border: "1px solid #78350f",
              boxShadow: "inset 0 0 3px rgba(0,0,0,0.4)"
            }}
          />
          <div>
            <span style={{ fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "#94a3b8" }}>
              {credential.category} CREDENTIAL
            </span>
            <h4 style={{ margin: "2px 0 0 0", fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>
              {credential.title}
            </h4>
          </div>
        </div>
        <StatusChip status={credential.status} size="sm" />
      </div>

      {/* Claims Preview */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: "8px",
          backgroundColor: "rgba(0, 0, 0, 0.25)",
          padding: "10px 12px",
          borderRadius: "10px",
          border: "1px solid rgba(255, 255, 255, 0.05)",
          margin: "10px 0"
        }}
      >
        {claimEntries.map(([key, val]) => (
          <div key={key}>
            <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>{key}</div>
            <div
              style={{
                fontSize: "0.82rem",
                fontWeight: 600,
                color: "#f1f5f9",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap"
              }}
            >
              {typeof val === "object" ? JSON.stringify(val) : String(val)}
            </div>
          </div>
        ))}
      </div>

      {/* Footer Info & Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "10px", paddingTop: "10px", borderTop: "1px solid rgba(255, 255, 255, 0.08)" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
          <span style={{ fontSize: "0.68rem", color: "#cbd5e1" }}>
            {credential.issuerName}
          </span>
          <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
            <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
            <span style={{ fontSize: "0.65rem", color: "#64748b" }}>
              Exp: {credential.expiryDate}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          {onPresent && (
            <button
              onClick={() => onPresent(credential)}
              title="Present with Selective Disclosure"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: "6px 10px",
                backgroundColor: "rgba(37, 99, 235, 0.8)",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer"
              }}
            >
              <QrCode size={14} />
              Share
            </button>
          )}

          {onViewDetails && (
            <button
              onClick={() => onViewDetails(credential)}
              title="Inspect Proof & JSON-LD"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: "6px 10px",
                backgroundColor: "rgba(255, 255, 255, 0.08)",
                color: "#e2e8f0",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                borderRadius: "8px",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer"
              }}
            >
              <Eye size={14} />
              Proof
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
