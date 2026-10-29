import React from "react";
import { IconAlertTriangle, IconCircleCheck, IconCircleDashed, IconCircleX, IconClock, IconHelpCircle } from "@tabler/icons-react";
import type { CredentialStatus } from "../../api/wallet.ts";
import type { RecoveryState } from "../../api/recovery.ts";
import { humanize } from "../../lib/format.ts";

import { recoveryTone, type BadgeTone } from "./tones.ts";

export type { BadgeTone };

const ICON_PROPS = { size: 14, stroke: 2, className: "me-1", "aria-hidden": true } as const;

const TONE_ICON: Record<BadgeTone, React.ReactNode> = {
  success: <IconCircleCheck {...ICON_PROPS} />,
  warning: <IconAlertTriangle {...ICON_PROPS} />,
  danger: <IconCircleX {...ICON_PROPS} />,
  info: <IconClock {...ICON_PROPS} />,
  neutral: <IconHelpCircle {...ICON_PROPS} />,
  brand: <IconCircleDashed {...ICON_PROPS} />,
};

/** Tabler "-lt" (light) badge colours per tone. */
const TONE_CLASS: Record<BadgeTone, string> = {
  success: "bg-green-lt",
  warning: "bg-yellow-lt",
  danger: "bg-red-lt",
  info: "bg-azure-lt",
  neutral: "bg-secondary-lt",
  brand: "bg-indigo-lt",
};

/** Text + icon + colour; colour is never the only signal. */
export const Badge: React.FC<{ tone: BadgeTone; children: React.ReactNode; title?: string }> = ({ tone, children, title }) => (
  <span className={`badge ${TONE_CLASS[tone]} d-inline-flex align-items-center`} title={title}>
    {TONE_ICON[tone]}
    {children}
  </span>
);

const CREDENTIAL_TONE: Record<CredentialStatus, BadgeTone> = {
  ACTIVE: "brand",
  SUSPENDED: "danger",
  REVOKED: "danger",
  EXPIRED: "warning",
  UNKNOWN: "neutral",
};

const CREDENTIAL_LABEL: Record<CredentialStatus, string> = {
  ACTIVE: "Active (stored status)",
  SUSPENDED: "Suspended",
  REVOKED: "Revoked",
  EXPIRED: "Expired",
  UNKNOWN: "Status unknown",
};

/** Stored lifecycle status. Deliberately not green: storing is not verifying. */
export const CredentialStatusBadge: React.FC<{ status: CredentialStatus }> = ({ status }) => (
  <Badge tone={CREDENTIAL_TONE[status]} title="Lifecycle status recorded by the Identity Service. This is not a verification result.">
    {CREDENTIAL_LABEL[status]}
  </Badge>
);

export const RecoveryStateBadge: React.FC<{ state: RecoveryState }> = ({ state }) => (
  <Badge tone={recoveryTone(state)}>{state === "UNKNOWN" ? "Unknown state" : humanize(state)}</Badge>
);
