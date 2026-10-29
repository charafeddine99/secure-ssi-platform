import React from "react";
import { IconCheck, IconCopy } from "@tabler/icons-react";
import { shortenIdentifier } from "../../lib/format.ts";

/**
 * Shows long DIDs / IDs without overflow. The full value stays available to
 * screen readers, as a tooltip and through the copy button.
 */
export const IdentifierText: React.FC<{ value: string; label?: string; wrap?: boolean; copy?: boolean }> = ({
  value, label = "identifier", wrap = false, copy = true,
}) => {
  const [copied, setCopied] = React.useState<"idle" | "done" | "failed">("idle");
  if (!value) return <span className="text-secondary">Not provided</span>;
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
    window.setTimeout(() => setCopied("idle"), 2000);
  };
  return (
    <span className="d-inline-flex align-items-center gap-1 mw-100 align-middle">
      <code className={wrap ? "text-break" : "text-truncate"} title={value}>
        <span aria-hidden="true">{wrap ? value : shortenIdentifier(value)}</span>
        <span className="visually-hidden">{value}</span>
      </code>
      {copy && (
        <button type="button" className="btn btn-ghost-secondary btn-icon btn-sm" onClick={onCopy} aria-label={`Copy ${label}`}>
          {copied === "done" ? <IconCheck size={16} aria-hidden="true" /> : <IconCopy size={16} aria-hidden="true" />}
          <span className="visually-hidden" aria-live="polite">{copied === "done" ? "Copied" : copied === "failed" ? "Copy failed" : ""}</span>
        </button>
      )}
    </span>
  );
};
