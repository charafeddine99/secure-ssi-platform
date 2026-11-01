import type { RecoveryPolicy } from "../../api/recovery.ts";
import { formatDuration } from "../../lib/format.ts";

/** Recovery policy form model; mirrors the Recovery Service invariants. */
export const HOUR = 3600;

export interface PolicyForm {
  minimumApprovals: string;
  maximumGuardians: string;
  approvalWindowHours: string;
  timeLockHours: string;
  expirationHours: string;
  maximumAttempts: string;
  cooldownHours: string;
  allowCancellation: boolean;
}

export function toForm(policy: RecoveryPolicy | null): PolicyForm {
  return {
    minimumApprovals: String(policy?.minimumApprovals ?? 2),
    maximumGuardians: String(policy?.maximumGuardians ?? 3),
    approvalWindowHours: String((policy?.approvalWindowSeconds ?? 72 * HOUR) / HOUR),
    timeLockHours: String((policy?.timeLockSeconds ?? 24 * HOUR) / HOUR),
    expirationHours: String((policy?.recoveryExpirationSeconds ?? 168 * HOUR) / HOUR),
    maximumAttempts: String(policy?.maximumAttempts ?? 3),
    cooldownHours: String((policy?.cooldownSeconds ?? 24 * HOUR) / HOUR),
    allowCancellation: policy?.allowCancellation ?? true,
  };
}

/** Mirrors the Recovery Service invariants so the user sees errors before submitting. */
export function validatePolicyForm(form: PolicyForm, walletId: string): { policy: RecoveryPolicy | null; errors: Partial<Record<keyof PolicyForm, string>> } {
  const errors: Partial<Record<keyof PolicyForm, string>> = {};
  const int = (key: keyof PolicyForm, min: number, max: number): number => {
    const value = Number(form[key]);
    if (!Number.isInteger(value) || value < min || value > max) errors[key] = `Enter a whole number from ${min} to ${max}.`;
    return value;
  };
  const hours = (key: keyof PolicyForm, minSeconds: number, maxSeconds: number): number => {
    const value = Math.round(Number(form[key]) * HOUR);
    if (!Number.isFinite(value) || value < minSeconds || value > maxSeconds) {
      errors[key] = `Enter between ${formatDuration(minSeconds)} and ${formatDuration(maxSeconds)}.`;
    }
    return value;
  };
  const minimumApprovals = int("minimumApprovals", 1, 32);
  const maximumGuardians = int("maximumGuardians", 1, 32);
  if (!errors.minimumApprovals && !errors.maximumGuardians && minimumApprovals > maximumGuardians) {
    errors.minimumApprovals = "Required approvals cannot exceed the number of guardians allowed.";
  }
  const approvalWindowSeconds = hours("approvalWindowHours", 60, 30 * 24 * HOUR);
  const timeLockSeconds = hours("timeLockHours", 0, 30 * 24 * HOUR);
  const recoveryExpirationSeconds = hours("expirationHours", 60, 60 * 24 * HOUR);
  if (!errors.expirationHours && recoveryExpirationSeconds < approvalWindowSeconds + timeLockSeconds) {
    errors.expirationHours = "Expiry must cover the approval window plus the time-lock.";
  }
  const maximumAttempts = int("maximumAttempts", 1, 20);
  const cooldownSeconds = hours("cooldownHours", 0, 30 * 24 * HOUR);
  if (Object.keys(errors).length > 0) return { policy: null, errors };
  return {
    policy: {
      walletId, minimumApprovals, maximumGuardians, approvalWindowSeconds, timeLockSeconds,
      recoveryExpirationSeconds, maximumAttempts, cooldownSeconds, allowCancellation: form.allowCancellation,
    },
    errors,
  };
}
