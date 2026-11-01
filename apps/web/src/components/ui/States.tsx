import React from "react";
import { IconAlertOctagon, IconBan, IconInbox, IconLock, IconWifiOff } from "@tabler/icons-react";
import { describeError, isApiError } from "../../lib/http.ts";
import { Button } from "./Button.tsx";

/** Tabler placeholder bar. */
export const Skeleton: React.FC<{ width?: string; size?: "xs" | "sm" | "lg" }> = ({ width = "100%", size }) => (
  <span className={["placeholder", size ? `placeholder-${size}` : "", "d-block mb-2"].filter(Boolean).join(" ")} style={{ width }} aria-hidden="true" />
);

export const LoadingState: React.FC<{ label?: string; rows?: number }> = ({ label = "Loading", rows = 3 }) => (
  <div className="placeholder-glow p-3" role="status" aria-live="polite" aria-busy="true">
    <span className="visually-hidden">{label}…</span>
    {Array.from({ length: rows }).map((_, index) => (
      <Skeleton key={index} size={index === 0 ? "lg" : undefined} width={index === 0 ? "40%" : `${90 - index * 12}%`} />
    ))}
  </div>
);

/** Tabler `.empty` block. */
export const EmptyState: React.FC<{
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  headingAs?: "p" | "h1" | "h2";
}> = ({ title, description, action, icon, headingAs: Title = "p" }) => (
  <div className="empty" role="status">
    <div className="empty-icon">{icon ?? <IconInbox size={48} stroke={1.5} aria-hidden="true" />}</div>
    <Title className="empty-title">{title}</Title>
    {description && <p className="empty-subtitle text-secondary">{description}</p>}
    {action && <div className="empty-action">{action}</div>}
  </div>
);

/** Explicitly marks a capability that the backend does not provide. */
export const NotAvailableState: React.FC<{ title: string; description: React.ReactNode }> = ({ title, description }) => (
  <div className="card">
    <div className="empty" role="note">
      <div className="empty-icon text-secondary"><IconBan size={48} stroke={1.5} aria-hidden="true" /></div>
      <p className="empty-title">{title}</p>
      <p className="empty-subtitle text-secondary">{description}</p>
    </div>
  </div>
);

export const ErrorState: React.FC<{
  error: unknown;
  title?: string;
  onRetry?: () => void;
}> = ({ error, title, onRetry }) => {
  const kind = isApiError(error) ? error.kind : "http";
  const icon = kind === "network" || kind === "timeout" || kind === "unavailable"
    ? <IconWifiOff size={48} stroke={1.5} aria-hidden="true" />
    : kind === "forbidden" || kind === "unauthorized"
      ? <IconLock size={48} stroke={1.5} aria-hidden="true" />
      : <IconAlertOctagon size={48} stroke={1.5} aria-hidden="true" />;
  const heading = title ?? (
    kind === "forbidden" ? "Access denied"
      : kind === "unauthorized" ? "Session ended"
        : kind === "not_found" ? "Not found"
          : "This information could not be loaded"
  );
  return (
    <div className="empty" role="alert">
      <div className="empty-icon text-danger">{icon}</div>
      <p className="empty-title">{heading}</p>
      <p className="empty-subtitle text-secondary">{describeError(error)}</p>
      {onRetry && kind !== "forbidden" && (
        <div className="empty-action"><Button variant="secondary" onClick={onRetry}>Try again</Button></div>
      )}
    </div>
  );
};
