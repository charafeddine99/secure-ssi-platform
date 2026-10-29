import React from "react";
import type { AsyncState } from "../../lib/useAsync.ts";
import { ErrorState, LoadingState } from "./States.tsx";

/** Render helper that keeps loading, error and success visually distinct. */
export function AsyncView<T>({
  state, children, loadingLabel, errorTitle, onRetry,
}: {
  state: AsyncState<T>;
  children: (data: T) => React.ReactNode;
  loadingLabel?: string;
  errorTitle?: string;
  onRetry?: () => void;
}): React.ReactElement {
  if (state.status === "loading") return <LoadingState label={loadingLabel} />;
  if (state.status === "error") return <ErrorState error={state.error} title={errorTitle} onRetry={onRetry} />;
  return <>{children(state.data)}</>;
}
