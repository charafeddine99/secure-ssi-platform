import React from "react";

export type TrustLevel = 
  | "STANDARDS_ALIGNED"
  | "PROTOTYPE_HIGH_ASSURANCE"
  | "BLOCKCHAIN_ANCHORED"
  | "ED25519_SIGNED"
  | "DEMO_TRUST_LEVEL";

interface TrustBadgeProps {
  level?: TrustLevel;
  label?: string;
  tooltip?: string;
  size?: "sm" | "md";
}

export const TrustBadge: React.FC<TrustBadgeProps> = ({
  level = "STANDARDS_ALIGNED",
  label,
  tooltip,
  size = "md"
}) => {
  const getBadgeConfig = () => {
    switch (level) {
      case "STANDARDS_ALIGNED":
        return {
          text: label || "Standards-Aligned",
          hint: tooltip || "Built to W3C VC 2.0 & EUDI ARF draft specifications (Academic Prototype)",
          icon: "🏛️",
          bg: "rgba(37, 99, 235, 0.12)",
          color: "#60a5fa",
          border: "rgba(37, 99, 235, 0.3)"
        };
      case "PROTOTYPE_HIGH_ASSURANCE":
        return {
          text: label || "Prototype High LoA",
          hint: tooltip || "Assurance level simulated according to ISO/IEC 29115 standards-alignment",
          icon: "🛡️",
          bg: "rgba(16, 185, 129, 0.12)",
          color: "#34d399",
          border: "rgba(16, 185, 129, 0.3)"
        };
      case "BLOCKCHAIN_ANCHORED":
        return {
          text: label || "EVM Anchored",
          hint: tooltip || "Anchored on Hardhat EVM Testnet smart contract",
          icon: "⛓️",
          bg: "rgba(147, 51, 234, 0.12)",
          color: "#c084fc",
          border: "rgba(147, 51, 234, 0.3)"
        };
      case "ED25519_SIGNED":
        return {
          text: label || "Ed25519 Verified",
          hint: tooltip || "W3C Data Integrity Linked Data cryptographic proof",
          icon: "🔑",
          bg: "rgba(14, 165, 233, 0.12)",
          color: "#38bdf8",
          border: "rgba(14, 165, 233, 0.3)"
        };
      case "DEMO_TRUST_LEVEL":
      default:
        return {
          text: label || "Demo Trust Level",
          hint: tooltip || "Academic prototype environment - Not officially certified",
          icon: "🔬",
          bg: "rgba(245, 158, 11, 0.12)",
          color: "#fbbf24",
          border: "rgba(245, 158, 11, 0.3)"
        };
    }
  };

  const config = getBadgeConfig();
  const isSmall = size === "sm";

  return (
    <span
      title={config.hint}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: isSmall ? "4px" : "6px",
        padding: isSmall ? "2px 8px" : "4px 10px",
        borderRadius: "9999px",
        fontSize: isSmall ? "0.7rem" : "0.75rem",
        fontWeight: 600,
        backgroundColor: config.bg,
        color: config.color,
        border: `1px solid ${config.border}`,
        letterSpacing: "0.02em",
        cursor: "help",
        whiteSpace: "nowrap"
      }}
    >
      <span style={{ fontSize: isSmall ? "0.75rem" : "0.85rem" }}>{config.icon}</span>
      <span>{config.text}</span>
    </span>
  );
};
