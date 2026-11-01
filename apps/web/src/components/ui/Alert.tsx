import React from "react";
import { IconAlertTriangle, IconCircleCheck, IconCircleX, IconInfoCircle } from "@tabler/icons-react";

export type AlertTone = "info" | "success" | "warning" | "danger" | "neutral";

const ICONS: Record<AlertTone, React.ReactNode> = {
  info: <IconInfoCircle className="alert-icon" aria-hidden="true" />,
  success: <IconCircleCheck className="alert-icon" aria-hidden="true" />,
  warning: <IconAlertTriangle className="alert-icon" aria-hidden="true" />,
  danger: <IconCircleX className="alert-icon" aria-hidden="true" />,
  neutral: <IconInfoCircle className="alert-icon" aria-hidden="true" />,
};

const TONE_CLASS: Record<AlertTone, string> = {
  info: "alert-info",
  success: "alert-success",
  warning: "alert-warning",
  danger: "alert-danger",
  neutral: "alert-secondary",
};

/** Tabler alert: alert-icon, alert-heading, alert-description. */
export const Alert: React.FC<{
  tone?: AlertTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  actions?: React.ReactNode;
  /** "alert" interrupts screen readers; use only for errors that need action. */
  live?: "polite" | "assertive" | "off";
  className?: string;
}> = ({ tone = "info", title, children, actions, live, className }) => {
  const role = live === "assertive" ? "alert" : live === "polite" ? "status" : undefined;
  return (
    <div className={["alert", TONE_CLASS[tone], "mb-0", className ?? ""].filter(Boolean).join(" ")} role={role}>
      {ICONS[tone]}
      <div>
        {title && <h4 className="alert-heading">{title}</h4>}
        {children && <div className="alert-description">{children}</div>}
        {actions && <div className="btn-list mt-2">{actions}</div>}
      </div>
    </div>
  );
};
