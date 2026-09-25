import React from "react";

export type StatusType = 
  | "ACTIVE"
  | "REVOKED"
  | "SUSPENDED"
  | "QUARANTINED"
  | "PENDING"
  | "VERIFIED"
  | "REJECTED";

interface StatusChipProps {
  status: StatusType | string;
  size?: "sm" | "md";
}

export const StatusChip: React.FC<StatusChipProps> = ({ status, size = "md" }) => {
  const norm = (status || "").toUpperCase();

  const getConfig = () => {
    switch (norm) {
      case "ACTIVE":
      case "VERIFIED":
        return {
          bg: "rgba(16, 185, 129, 0.12)",
          color: "#34d399",
          border: "rgba(16, 185, 129, 0.25)",
          dot: "#10b981",
          label: norm === "ACTIVE" ? "Active" : "Verified"
        };
      case "REVOKED":
      case "REJECTED":
        return {
          bg: "rgba(239, 68, 68, 0.12)",
          color: "#f87171",
          border: "rgba(239, 68, 68, 0.25)",
          dot: "#ef4444",
          label: norm === "REVOKED" ? "Revoked" : "Rejected"
        };
      case "QUARANTINED":
        return {
          bg: "rgba(220, 38, 38, 0.2)",
          color: "#fca5a5",
          border: "rgba(220, 38, 38, 0.4)",
          dot: "#dc2626",
          label: "Quarantined"
        };
      case "SUSPENDED":
      case "PENDING":
        return {
          bg: "rgba(245, 158, 11, 0.12)",
          color: "#fbbf24",
          border: "rgba(245, 158, 11, 0.25)",
          dot: "#f59e0b",
          label: norm === "PENDING" ? "Pending" : "Suspended"
        };
      default:
        return {
          bg: "rgba(148, 163, 184, 0.12)",
          color: "#cbd5e1",
          border: "rgba(148, 163, 184, 0.25)",
          dot: "#94a3b8",
          label: norm
        };
    }
  };

  const config = getConfig();
  const isSm = size === "sm";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: isSm ? "2px 8px" : "4px 10px",
        borderRadius: "9999px",
        fontSize: isSm ? "0.7rem" : "0.75rem",
        fontWeight: 600,
        backgroundColor: config.bg,
        color: config.color,
        border: `1px solid ${config.border}`,
        letterSpacing: "0.03em"
      }}
    >
      <span
        style={{
          width: isSm ? "5px" : "6px",
          height: isSm ? "5px" : "6px",
          borderRadius: "50%",
          backgroundColor: config.dot
        }}
      />
      {config.label}
    </span>
  );
};
