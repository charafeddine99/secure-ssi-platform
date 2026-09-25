import React from "react";
import { CheckCircle2, XCircle, Clock, ShieldCheck, AlertTriangle } from "lucide-react";

export interface VerificationStep {
  id: string;
  title: string;
  description: string;
  status: "SUCCESS" | "FAILED" | "PENDING" | "WARNING";
  latencyMs?: number;
  details?: string;
}

interface VerificationChecklistProps {
  steps: VerificationStep[];
}

export const VerificationChecklist: React.FC<VerificationChecklistProps> = ({ steps }) => {
  const getStatusIcon = (status: VerificationStep["status"]) => {
    switch (status) {
      case "SUCCESS":
        return <CheckCircle2 size={18} color="#34d399" />;
      case "FAILED":
        return <XCircle size={18} color="#f87171" />;
      case "WARNING":
        return <AlertTriangle size={18} color="#fbbf24" />;
      case "PENDING":
      default:
        return <Clock size={18} color="#94a3b8" />;
    }
  };

  const getBorderColor = (status: VerificationStep["status"]) => {
    switch (status) {
      case "SUCCESS":
        return "rgba(16, 185, 129, 0.3)";
      case "FAILED":
        return "rgba(239, 68, 68, 0.3)";
      case "WARNING":
        return "rgba(245, 158, 11, 0.3)";
      case "PENDING":
      default:
        return "#1f2937";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {steps.map((step, idx) => (
        <div
          key={step.id}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "12px",
            padding: "12px 14px",
            borderRadius: "10px",
            backgroundColor: "#0d131f",
            border: `1px solid ${getBorderColor(step.status)}`
          }}
        >
          <div style={{ marginTop: "2px" }}>{getStatusIcon(step.status)}</div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc" }}>
                {idx + 1}. {step.title}
              </span>
              {step.latencyMs !== undefined && (
                <span style={{ fontSize: "0.72rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                  {step.latencyMs.toFixed(2)} ms
                </span>
              )}
            </div>
            <p style={{ margin: "2px 0 0 0", fontSize: "0.75rem", color: "#94a3b8" }}>
              {step.description}
            </p>
            {step.details && (
              <div
                style={{
                  marginTop: "6px",
                  padding: "6px 8px",
                  borderRadius: "6px",
                  backgroundColor: "rgba(0, 0, 0, 0.3)",
                  fontSize: "0.72rem",
                  fontFamily: "var(--font-mono)",
                  color: "#cbd5e1"
                }}
              >
                {step.details}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
