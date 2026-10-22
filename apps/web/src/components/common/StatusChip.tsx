import React from "react";
import { ShieldCheck, XCircle, AlertTriangle, Clock, RefreshCw, HelpCircle } from "lucide-react";

export type StatusType = 
  | "ACTIVE"
  | "REVOKED"
  | "EXPIRED"
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
  const isSm = size === "sm";
  const iconSize = isSm ? 12 : 14;

  const getConfig = () => {
    switch (norm) {
      case "ACTIVE":
      case "VERIFIED":
        return {
          bg: "rgba(22, 163, 74, 0.15)",
          color: "#4ade80",
          border: "rgba(22, 163, 74, 0.4)",
          icon: <ShieldCheck size={iconSize} />,
          label: norm === "ACTIVE" ? "Active" : "Verified"
        };
      case "REVOKED":
      case "REJECTED":
        return {
          bg: "rgba(220, 38, 38, 0.15)",
          color: "#f87171",
          border: "rgba(220, 38, 38, 0.4)",
          icon: <XCircle size={iconSize} />,
          label: norm === "REVOKED" ? "Revoked" : "Rejected"
        };
      case "QUARANTINED":
      case "QUARANTINE":
        return {
          bg: "rgba(234, 88, 12, 0.15)",
          color: "#fb923c",
          border: "rgba(234, 88, 12, 0.4)",
          icon: <AlertTriangle size={iconSize} />,
          label: "Quarantine"
        };
      case "EXPIRED":
        return {
          bg: "rgba(217, 119, 6, 0.15)",
          color: "#fbbf24",
          border: "rgba(217, 119, 6, 0.4)",
          icon: <Clock size={iconSize} />,
          label: "Expired"
        };
      case "SUSPENDED":
        return {
          bg: "rgba(217, 119, 6, 0.15)",
          color: "#fbbf24",
          border: "rgba(217, 119, 6, 0.4)",
          icon: <AlertTriangle size={iconSize} />,
          label: "Suspended"
        };
      case "PENDING":
        return {
          bg: "rgba(37, 99, 235, 0.15)",
          color: "#60a5fa",
          border: "rgba(37, 99, 235, 0.4)",
          icon: <RefreshCw size={iconSize} className="spin" />,
          label: "Pending"
        };
      default:
        return {
          bg: "rgba(100, 116, 139, 0.15)",
          color: "#cbd5e1",
          border: "rgba(100, 116, 139, 0.35)",
          icon: <HelpCircle size={iconSize} />,
          label: norm.replace(/_/g, " ") || "Unknown"
        };
    }
  };

  const config = getConfig();

  return (
    <span
      role="status"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
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
      <span aria-hidden="true" style={{ display: "inline-flex", alignItems: "center" }}>
        {config.icon}
      </span>
      <span>{config.label}</span>
    </span>
  );
};
