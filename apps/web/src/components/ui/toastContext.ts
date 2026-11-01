import React from "react";

export type ToastTone = "success" | "danger" | "info";

export const ToastContext = React.createContext<((tone: ToastTone, message: string) => void) | null>(null);

export function useToast(): (tone: ToastTone, message: string) => void {
  const push = React.useContext(ToastContext);
  if (!push) throw new Error("useToast must be used inside <ToastProvider>.");
  return push;
}
