import React from "react";
import { createPortal } from "react-dom";
import { Button, type ButtonVariant } from "./Button.tsx";

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Tabler modal (modal-blur, modal-dialog-centered) driven by React state:
 * focus moves inside, Tab is trapped, Escape closes, and focus returns to
 * the opener on close (WCAG 2.4.3 / 2.1.2).
 */
export const Dialog: React.FC<{
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  actions?: React.ReactNode;
  closeOnBackdrop?: boolean;
  status?: "danger" | "success" | "warning" | "primary";
}> = ({ open, title, onClose, children, actions, closeOnBackdrop = true, status }) => {
  const dialogRef = React.useRef<HTMLDivElement>(null);
  const titleId = React.useId();
  const descriptionId = React.useId();

  React.useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const node = dialogRef.current;
    const first = node?.querySelector<HTMLElement>(".modal-body " + FOCUSABLE.split(", ").join(", .modal-body "))
      ?? node?.querySelector<HTMLElement>(".modal-footer button:not([disabled])");
    (first ?? node)?.focus();
    document.body.classList.add("modal-open");
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!items.length) return;
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("modal-open");
      opener?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <>
      <div
        className="modal modal-blur show d-block"
        tabIndex={-1}
        onMouseDown={(event) => {
          if (closeOnBackdrop && event.target === event.currentTarget) onClose();
        }}
      >
        <div className="modal-dialog modal-dialog-centered" role="document">
          <div
            ref={dialogRef}
            className="modal-content"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            tabIndex={-1}
          >
            {status && <div className={`modal-status bg-${status}`} />}
            <div className="modal-header">
              <h2 id={titleId} className="modal-title">{title}</h2>
              <button type="button" className="btn-close" aria-label="Close" onClick={onClose} />
            </div>
            <div id={descriptionId} className="modal-body">{children}</div>
            {actions && <div className="modal-footer">{actions}</div>}
          </div>
        </div>
      </div>
      <div className="modal-backdrop show" />
    </>,
    document.body,
  );
};

export const ConfirmDialog: React.FC<{
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  confirmVariant?: ButtonVariant;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ open, title, children, confirmLabel, confirmVariant = "primary", busy = false, onConfirm, onCancel }) => (
  <Dialog
    open={open}
    title={title}
    status={confirmVariant === "danger" ? "danger" : undefined}
    onClose={() => { if (!busy) onCancel(); }}
    closeOnBackdrop={!busy}
    actions={(
      <>
        <Button variant="secondary" className="me-auto" onClick={onCancel} disabled={busy}>Cancel</Button>
        <Button variant={confirmVariant} onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
      </>
    )}
  >
    {children}
  </Dialog>
);
