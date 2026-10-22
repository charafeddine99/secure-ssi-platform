import React, { useEffect, useState } from "react";
import { Modal } from "../common/Modal";
import { CheckCircle2, Lock } from "lucide-react";
import { CredentialCardData } from "../credentials/CredentialCard";

interface SelectiveDisclosureSheetProps {
  isOpen: boolean;
  onClose: () => void;
  credential: CredentialCardData | null;
  verifierName?: string;
  verifierPurpose?: string;
  requiredClaims?: string[];
  onConfirmPresentation: () => void;
}

export const SelectiveDisclosureSheet: React.FC<SelectiveDisclosureSheetProps> = ({
  isOpen,
  onClose,
  credential,
  verifierName = "Verifier",
  verifierPurpose = "Credential verification",
  requiredClaims = [],
  onConfirmPresentation,
}) => {
  const [consentConfirmed, setConsentConfirmed] = useState(false);

  useEffect(() => {
    setConsentConfirmed(false);
  }, [isOpen, credential?.id]);

  if (!isOpen || !credential) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Consent to share signed credential"
      subtitle={`Verifier: ${verifierName}`}
      maxWidth="600px"
    >
      <div style={{ backgroundColor: "#161f33", padding: "14px 16px", borderRadius: "10px", border: "1px solid #1f2937", marginBottom: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#60a5fa", fontSize: "0.85rem", fontWeight: 600 }}>
          <Lock size={16} />
          <span>Requested purpose</span>
        </div>
        <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "#cbd5e1" }}>{verifierPurpose}</p>
      </div>

      <div role="note" style={{ backgroundColor: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.35)", color: "#fcd34d", padding: "12px 14px", borderRadius: "8px", marginBottom: "16px", fontSize: "0.8rem", lineHeight: 1.5 }}>
        This profile sends the complete signed credential. The current Data Integrity proof does not support claim-level cryptographic selective disclosure, so unselected claims cannot be hidden.
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "18px" }}>
        <div style={{ fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Claims included in the complete credential
        </div>
        {Object.entries(credential.claims || {}).map(([key, value]) => (
          <div key={key} style={{ padding: "10px 12px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937" }}>
            <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#f8fafc" }}>
              {key}{requiredClaims.includes(key) ? " (requested)" : ""}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#cbd5e1", overflowWrap: "anywhere" }}>
              {typeof value === "string" ? value : JSON.stringify(value)}
            </div>
          </div>
        ))}
      </div>

      <label style={{ display: "flex", alignItems: "flex-start", gap: "9px", color: "#e2e8f0", fontSize: "0.8rem", lineHeight: 1.5, marginBottom: "18px" }}>
        <input
          type="checkbox"
          checked={consentConfirmed}
          onChange={(event) => setConsentConfirmed(event.target.checked)}
          style={{ marginTop: "3px", accentColor: "#2563eb" }}
        />
        I understand that approving shares this entire signed credential, including every claim listed above.
      </label>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", borderTop: "1px solid #1f2937", paddingTop: "16px" }}>
        <button type="button" onClick={onClose} style={{ padding: "8px 16px", backgroundColor: "#1f2937", color: "#e2e8f0", border: "1px solid #374151", borderRadius: "8px", fontSize: "0.85rem", fontWeight: 600, cursor: "pointer" }}>
          Cancel
        </button>
        <button
          type="button"
          disabled={!consentConfirmed}
          onClick={() => {
            onConfirmPresentation();
            onClose();
          }}
          style={{ padding: "8px 20px", backgroundColor: consentConfirmed ? "#2563eb" : "#334155", color: "#ffffff", border: "none", borderRadius: "8px", fontSize: "0.85rem", fontWeight: 600, cursor: consentConfirmed ? "pointer" : "not-allowed", display: "inline-flex", alignItems: "center", gap: "6px" }}
        >
          <CheckCircle2 size={16} />
          Approve full credential
        </button>
      </div>
    </Modal>
  );
};
