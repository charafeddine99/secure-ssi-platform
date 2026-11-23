import React from "react";

export type Run = <T>(action: string, resource: string, operation: (token: string | null) => Promise<T>) => Promise<T>;

export class StepUpCancelledError extends Error {
  constructor() {
    super("Authenticator confirmation was cancelled. Nothing was changed.");
    this.name = "StepUpCancelledError";
  }
}

export const StepUpContext = React.createContext<Run | null>(null);

export function useStepUp(): Run {
  const context = React.useContext(StepUpContext);
  if (context === null) throw new Error("useStepUp needs a StepUpProvider.");
  return context;
}
