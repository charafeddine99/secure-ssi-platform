import React from "react";
import { ShieldAlert, ShieldCheck, AlertTriangle, Cpu } from "lucide-react";

interface RiskScorePanelProps {
  score: number;
  isFraudulent?: boolean;
  anomalyScore?: number;
  xgboostProbability?: number;
  reconstructionMse?: number;
  reasons?: string[];
  evaluationLatencyMs?: number;
}

export const RiskScorePanel: React.FC<RiskScorePanelProps> = ({
  score,
  isFraudulent,
  anomalyScore,
  xgboostProbability,
  reconstructionMse,
  reasons = [],
  evaluationLatencyMs
}) => {
  const getSeverity = () => {
    if (score > 70) return { label: "CRITICAL RISK", color: "#f87171", bg: "rgba(239, 68, 68, 0.15)", border: "rgba(239, 68, 68, 0.4)" };
    if (score > 40) return { label: "MODERATE RISK", color: "#fbbf24", bg: "rgba(245, 158, 11, 0.15)", border: "rgba(245, 158, 11, 0.4)" };
    return { label: "LOW RISK (NORMAL)", color: "#34d399", bg: "rgba(16, 185, 129, 0.15)", border: "rgba(16, 185, 129, 0.4)" };
  };

  const sev = getSeverity();

  return (
    <div
      style={{
        backgroundColor: "#111827",
        borderRadius: "14px",
        border: `1px solid ${sev.border}`,
        padding: "18px",
        display: "flex",
        flexDirection: "column",
        gap: "14px"
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Cpu size={18} color="#60a5fa" />
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>
            AI Hybrid Threat Engine
          </span>
        </div>
        <span
          style={{
            fontSize: "0.72rem",
            fontWeight: 700,
            padding: "3px 10px",
            borderRadius: "9999px",
            backgroundColor: sev.bg,
            color: sev.color,
            border: `1px solid ${sev.border}`
          }}
        >
          {sev.label}
        </span>
      </div>

      {/* Score Meter */}
      <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
        <span style={{ fontSize: "2.2rem", fontWeight: 800, color: sev.color, lineHeight: 1 }}>
          {score}
        </span>
        <span style={{ fontSize: "0.9rem", color: "#94a3b8" }}>/ 100 Risk Score</span>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: "100%",
          height: "8px",
          backgroundColor: "#1f2937",
          borderRadius: "9999px",
          overflow: "hidden"
        }}
      >
        <div
          style={{
            width: `${Math.min(100, Math.max(0, score))}%`,
            height: "100%",
            backgroundColor: sev.color,
            transition: "width 0.4s ease"
          }}
        />
      </div>

      {/* ML Model Decomposition */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "10px",
          backgroundColor: "#0d131f",
          padding: "12px",
          borderRadius: "8px",
          border: "1px solid #1f2937",
          fontSize: "0.75rem"
        }}
      >
        <div>
          <span style={{ color: "#94a3b8" }}>XGBoost Split Prob:</span>
          <div style={{ fontWeight: 600, color: "#60a5fa", marginTop: "2px", fontFamily: "var(--font-mono)" }}>
            {xgboostProbability !== undefined ? `${(xgboostProbability * 100).toFixed(1)}%` : "N/A"}
          </div>
        </div>

        <div>
          <span style={{ color: "#94a3b8" }}>Autoencoder Latent MSE:</span>
          <div style={{ fontWeight: 600, color: "#c084fc", marginTop: "2px", fontFamily: "var(--font-mono)" }}>
            {reconstructionMse !== undefined ? reconstructionMse.toFixed(4) : "N/A"}
          </div>
        </div>
      </div>

      {/* Anomaly reasons */}
      {reasons.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <span style={{ fontSize: "0.72rem", color: "#94a3b8", textTransform: "uppercase" }}>
            Detection Factors & Reasoning:
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {reasons.map((r, i) => (
              <span
                key={i}
                style={{
                  fontSize: "0.72rem",
                  padding: "4px 8px",
                  borderRadius: "6px",
                  backgroundColor: score > 70 ? "rgba(239, 68, 68, 0.12)" : "#161f33",
                  color: score > 70 ? "#fca5a5" : "#cbd5e1",
                  border: score > 70 ? "1px solid rgba(239, 68, 68, 0.25)" : "1px solid #1f2937"
                }}
              >
                {r}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
