import type { AuditLogEntry } from "../../api/admin.ts";

function csvCell(value: string): string {
  // Prevent spreadsheet formula injection and escape quotes.
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return `"${safe.replace(/"/g, '""')}"`;
}

export function auditCsv(rows: AuditLogEntry[]): string {
  const header = ["ID", "Event type", "Actor DID", "Target wallet", "Risk score", "Timestamp"];
  return [header, ...rows.map((r) => [r.id, r.eventType, r.actorDid, r.targetWallet ?? "", r.riskScore === null ? "" : String(r.riskScore), r.createdAt])]
    .map((cols) => cols.map((c) => csvCell(String(c))).join(","))
    .join("\n");
}
