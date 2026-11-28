/**
 * What the credential card says about lifecycle status. Pure, so every state
 * can be tested without a browser.
 *
 * - Past validUntil wins: an expired credential is never shown as valid.
 * - While the issuer is being asked, the card says "Checking…" (stored, not yet verified).
 * - If the check fails, the card says "Unknown"; it never falls back to the stored value.
 */
export type LiveStatus = "ACTIVE" | "SUSPENDED" | "REVOKED" | "EXPIRED" | "UNKNOWN";

export type LiveCheck =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; data: { status: LiveStatus } };

export interface CardStatus {
  key: "valid" | "checking" | "unknown" | "expired" | "not-yet-valid" | "revoked" | "suspended";
  text: string;
  /** Only a valid or still-checking credential keeps its full colour. */
  inactive: boolean;
  /** Why Present is blocked, or null when the wallet may offer it. The verifier still checks everything. */
  blocked: string | null;
}

const BLOCKED: Partial<Record<CardStatus["key"], string>> = {
  revoked: "The issuer revoked this credential.",
  suspended: "The issuer suspended this credential.",
  expired: "This credential has expired.",
  "not-yet-valid": "This credential is not valid yet.",
};

const TEXT: Record<LiveStatus, string> = {
  ACTIVE: "Active",
  SUSPENDED: "Suspended",
  REVOKED: "Revoked",
  EXPIRED: "Expired",
  UNKNOWN: "Unknown",
};

function expired(validUntil: string | null | undefined, now: number): boolean {
  if (!validUntil) return false;
  const time = new Date(validUntil).getTime();
  return Number.isFinite(time) && time < now;
}

function notYetValid(validFrom: string | null | undefined, now: number): boolean {
  if (!validFrom) return false;
  const time = new Date(validFrom).getTime();
  return Number.isFinite(time) && time > now;
}

/**
 * "Active" means only that the issuer's status list does not mark it revoked or
 * suspended and the dates allow it. It says nothing about signature or trust.
 */
export function cardStatus(
  validUntil: string | null | undefined,
  live: LiveCheck,
  now = Date.now(),
  validFrom?: string | null,
): CardStatus {
  const make = (key: CardStatus["key"], text: string): CardStatus => ({
    key,
    text,
    inactive: key !== "valid" && key !== "checking",
    blocked: BLOCKED[key] ?? null,
  });
  if (expired(validUntil, now)) return make("expired", "Expired");
  if (notYetValid(validFrom, now)) return make("not-yet-valid", "Not yet valid");
  if (live.status === "loading") return make("checking", "Checking…");
  if (live.status === "error") return make("unknown", "Unknown");
  const value = live.data.status;
  const key = value === "ACTIVE" ? "valid" : (value.toLowerCase() as CardStatus["key"]);
  return make(key, TEXT[value] ?? "Unknown");
}
