import type { RecoveryState } from "../../api/recovery.ts";

export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral" | "brand";

export function recoveryTone(state: RecoveryState): BadgeTone {
  switch (state) {
    case "COMPLETED": return "success";
    case "REJECTED":
    case "FAILED":
    case "EXPIRED": return "danger";
    case "CANCELLED": return "neutral";
    case "RECONCILIATION_REQUIRED": return "warning";
    case "UNKNOWN": return "neutral";
    default: return "info";
  }
}
