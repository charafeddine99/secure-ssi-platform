import React from "react";
import { IconCircleCheck, IconCircleX, IconInfoCircle } from "@tabler/icons-react";

import { ToastContext, type ToastTone } from "./toastContext.ts";

interface ToastItem { id: number; tone: ToastTone; message: string }

const TONE_TEXT: Record<ToastTone, string> = { success: "text-success", danger: "text-danger", info: "text-azure" };
const TONE_TITLE: Record<ToastTone, string> = { success: "Done", danger: "Action failed", info: "Notice" };

/** Tabler toast stack (toast-container, toast-header, toast-body). */
export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = React.useState<ToastItem[]>([]);
  const counter = React.useRef(0);
  const dismiss = React.useCallback((id: number) => setItems((all) => all.filter((item) => item.id !== id)), []);
  const push = React.useCallback((tone: ToastTone, message: string) => {
    counter.current += 1;
    const id = counter.current;
    setItems((all) => [...all.slice(-3), { id, tone, message }]);
    window.setTimeout(() => dismiss(id), tone === "danger" ? 10_000 : 6_000);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-container position-fixed bottom-0 end-0 p-3" aria-live="polite" aria-relevant="additions">
        {items.map((item) => (
          <div key={item.id} className="toast show" role={item.tone === "danger" ? "alert" : "status"}>
            <div className="toast-header">
              <span className={`me-2 ${TONE_TEXT[item.tone]}`} aria-hidden="true">
                {item.tone === "success" ? <IconCircleCheck size={18} /> : item.tone === "danger" ? <IconCircleX size={18} /> : <IconInfoCircle size={18} />}
              </span>
              <strong className="me-auto">{TONE_TITLE[item.tone]}</strong>
              <button type="button" className="btn-close" onClick={() => dismiss(item.id)} aria-label="Dismiss notification" />
            </div>
            <div className="toast-body">{item.message}</div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};
