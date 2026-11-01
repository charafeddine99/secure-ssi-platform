/** Formatting helpers. Dates are shown in the viewer's locale with explicit time zone. */

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid date";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid date";
  return date.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "Unknown";
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round((minutes / 60) * 10) / 10;
  if (hours < 48) return `${hours} h`;
  return `${Math.round(hours / 24)} days`;
}

/** Humanise identifiers such as "UniversityAffiliationCredential" or "PENDING_APPROVALS". */
export function humanize(value: string): string {
  if (!value) return "";
  if (/^[A-Z0-9_]+$/.test(value) || /^[a-z0-9]+(_[a-z0-9]+)+$/.test(value)) {
    return value.toLowerCase().split("_").map((part, index) => (index === 0 ? part.charAt(0).toUpperCase() + part.slice(1) : part)).join(" ");
  }
  return value.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/^./, (c) => c.toUpperCase());
}

export function shortenIdentifier(value: string, head = 18, tail = 8): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

export function renderClaimValue(value: unknown): string {
  if (value === null || value === undefined) return "Not provided";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "Unsupported value";
  }
}

export function isExpired(validUntil: string | null | undefined, now = Date.now()): boolean {
  if (!validUntil) return false;
  const time = new Date(validUntil).getTime();
  return Number.isFinite(time) && time < now;
}
