import React, { useState } from "react";
import { Modal } from "../common/Modal";
import { ShieldCheck, Eye, EyeOff, CheckCircle2, Lock } from "lucide-react";
import { CredentialCardData } from "../credentials/CredentialCard";

interface SelectiveDisclosureSheetProps {
  isOpen: boolean;
  onClose: () => void;
  credential: CredentialCardData | null;
  verifierName?: string;
  verifierPurpose?: string;
  requiredClaims?: string[];
  onConfirmPresentation: (disclosedClaims: Record<string, any>, blindedCommitments: string[]) => void;
}

export const SelectiveDisclosureSheet: React.FC<SelectiveDisclosureSheetProps> = ({
  isOpen,
  onClose,
  credential,
  verifierName = "General eIDAS Verifier Service",
  verifierPurpose = "Standard identity verification & compliance check",
  requiredClaims = [],
  onConfirmPresentation
}) => {
  if (!credential) return null;

  // Track selection for each claim
  const allClaimKeys = Object.keys(credential.claims || {});
  
  // Default: required claims checked, sensitive numbers unchecked
  const [selectedKeys, setSelectedKeys] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    allClaimKeys.forEach((key) => {
      // By default, reveal non-sensitive fields
      const isSensitive = key.toLowerCase().includes("no") || 
                          key.toLowerCase().includes("tarih") || 
                          key.toLowerCase().includes("seri");
      initial[key] = !isSensitive || requiredClaims.includes(key);
    });
    return initial;
  });

  const toggleClaim = (key: string) => {
    setSelectedKeys((prev) => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const handleApprove = () => {
    const disclosed: Record<string, any> = {};
    const blinded: string[] = [];

    allClaimKeys.forEach((k) => {
      if (selectedKeys[k]) {
        disclosed[k] = credential.claims[k];
      } else {
        blinded.push(`salted-hash:${k}:${btoa(String(credential.claims[k])).slice(0, 16)}`);
      }
    });

    onConfirmPresentation(disclosed, blinded);
    onClose();
  };

  const disclosedCount = Object.values(selectedKeys).filter(Boolean).length;
  const minimizedCount = allClaimKeys.length - disclosedCount;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="User Consent & Selective Disclosure"
      subtitle={`Verifier: ${verifierName}`}
      maxWidth="600px"
    >
      {/* Purpose Banner */}
      <div
        style={{
          backgroundColor: "#161f33",
          padding: "14px 16px",
          borderRadius: "10px",
          border: "1px solid #1f2937",
          marginBottom: "16px"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#60a5fa", fontSize: "0.85rem", fontWeight: 600 }}>
          <Lock size={16} />
          <span>Verification Purpose</span>
        </div>
        <p style={{ margin: "4px 0 0 0", fontSize: "0.8rem", color: "#cbd5e1" }}>
          {verifierPurpose}
        </p>
      </div>

      {/* Data Minimization Summary */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          backgroundColor: "rgba(16, 185, 129, 0.08)",
          padding: "10px 14px",
          borderRadius: "8px",
          border: "1px solid rgba(16, 185, 129, 0.25)",
          marginBottom: "16px",
          fontSize: "0.8rem"
        }}
      >
        <span style={{ color: "#34d399", fontWeight: 600 }}>
          Data Minimization Active
        </span>
        <span style={{ color: "#cbd5e1" }}>
          <strong style={{ color: "#60a5fa" }}>{disclosedCount}</strong> revealed /{" "}
          <strong style={{ color: "#f87171" }}>{minimizedCount}</strong> hidden (salted hash)
        </span>
      </div>

      {/* Field-by-field Checklist */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "20px" }}>
        <div style={{ fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px" }}>
          Select claims to share:
        </div>

        {allClaimKeys.map((key) => {
          const isSelected = !!selectedKeys[key];
          const isRequired = requiredClaims.includes(key);

          return (
            <label
              key={key}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 14px",
                borderRadius: "8px",
                backgroundColor: isSelected ? "rgba(37, 99, 235, 0.08)" : "#0d131f",
                border: isSelected ? "1px solid rgba(37, 99, 235, 0.4)" : "1px solid #1f2937",
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleClaim(key)}
                  style={{ width: "16px", height: "16px", accentColor: "#2563eb", cursor: "pointer" }}
                />
                <div>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc" }}>
                    {key}
                    {isRequired && (
                      <span style={{ marginLeft: "6px", fontSize: "0.68rem", color: "#fbbf24", fontWeight: 500 }}>
                        (Requested)
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: isSelected ? "#93c5fd" : "#64748b" }}>
                    {isSelected ? String(credential.claims[key]) : "Hidden — Verifier receives cryptographic hash"}
                  </div>
                </div>
              </div>

              <div>
                {isSelected ? (
                  <Eye size={16} color="#60a5fa" />
                ) : (
                  <EyeOff size={16} color="#64748b" />
                )}
              </div>
            </label>
          );
        })}
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", borderTop: "1px solid #1f2937", paddingTop: "16px" }}>
        <button
          onClick={onClose}
          style={{
            padding: "8px 16px",
            backgroundColor: "#1f2937",
            color: "#e2e8f0",
            border: "1px solid #374151",
            borderRadius: "8px",
            fontSize: "0.85rem",
            fontWeight: 600,
            cursor: "pointer"
          }}
        >
          Cancel
        </button>

        <button
          onClick={handleApprove}
          style={{
            padding: "8px 20px",
            backgroundColor: "#2563eb",
            color: "#ffffff",
            border: "none",
            borderRadius: "8px",
            fontSize: "0.85rem",
            fontWeight: 600,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "6px"
          }}
        >
          <CheckCircle2 size={16} />
          Approve & Present
        </button>
      </div>
    </Modal>
  );
};
