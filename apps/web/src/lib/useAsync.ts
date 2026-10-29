import { useCallback, useEffect, useRef, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "success"; data: T; error: null }
  | { status: "error"; data: null; error: unknown };

/**
 * Load data with explicit loading / success / error states. An error is never
 * converted into an empty value, so screens can show the failure truthfully.
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading", data: null, error: null });
  const [version, setVersion] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });
    loadRef.current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: "success", data, error: null });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ status: "error", data: null, error });
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  return { ...state, reload };
}
