import React from "react";
import { Cpu } from "lucide-react";

interface RiskScorePanelProps {
  score: number;
  modelVersion?: string;
  reasons?: string[];
  advisoryOnly?: boolean;
}

export const RiskScorePanel: React.FC<RiskScorePanelProps> = ({
  score,
  modelVersion,
  reasons = [],
  advisoryOnly = true
}) => {
  const severity = score >= 85
    ? { label: "HIGH HEURISTIC SIGNAL", color: "#f87171", border: "rgba(239, 68, 68, 0.4)" }
    : score >= 40
      ? { label: "ELEVATED HEURISTIC SIGNAL", color: "#fbbf24", border: "rgba(245, 158, 11, 0.4)" }
      : { label: "LOW HEURISTIC SIGNAL", color: "#34d399", border: "rgba(16, 185, 129, 0.4)" };

  return (
    <section style={{ backgroundColor: "#111827", borderRadius: "14px", border: `1px solid ${severity.border}`, padding: "18px", display: "flex", flexDirection: "column", gap: "14px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Cpu size={18} color="#60a5fa" />
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>Deterministic risk heuristic</span>
        </div>
        <span style={{ fontSize: "0.72rem", fontWeight: 700, color: severity.color }}>{severity.label}</span>
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
        <span style={{ fontSize: "2.2rem", fontWeight: 800, color: severity.color, lineHeight: 1 }}>{score}</span>
        <span style={{ fontSize: "0.9rem", color: "#94a3b8" }}>/ 100 heuristic score</span>
      </div>
      <div style={{ width: "100%", height: "8px", backgroundColor: "#1f2937", borderRadius: "9999px", overflow: "hidden" }}>
        <div style={{ width: `${Math.min(100, Math.max(0, score))}%`, height: "100%", backgroundColor: severity.color }} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Rule version: {modelVersion || "not reported"}</span>
        <span style={{ fontSize: "0.72rem", color: "#fbbf24" }}>
          {advisoryOnly ? "Advisory only. This score does not establish credential validity or issuer trust." : "Service did not confirm advisory-only semantics."}
        </span>
      </div>

      {reasons.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <span style={{ fontSize: "0.72rem", color: "#94a3b8", textTransform: "uppercase" }}>Reported heuristic reasons</span>
          {reasons.map((reason, index) => (
            <span key={`${index}-${reason}`} style={{ fontSize: "0.72rem", color: "#cbd5e1", backgroundColor: "#161f33", border: "1px solid #1f2937", borderRadius: "6px", padding: "5px 8px" }}>
              {reason}
            </span>
          ))}
        </div>
      )}
    </section>
  );
};
