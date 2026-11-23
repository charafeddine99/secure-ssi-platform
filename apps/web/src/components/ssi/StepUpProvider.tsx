import React from "react";
import { fetchMfaStatus, fetchSecurityKeyStatus, requestStepUpToken, stepUpWithSecurityKey } from "../../api/stepUp.ts";
import { Dialog } from "../ui/Dialog.tsx";
import { Button } from "../ui/Button.tsx";
import { TextField } from "../ui/Field.tsx";
import { Alert } from "../ui/Alert.tsx";
import { describeError } from "../../lib/http.ts";

import { StepUpCancelledError, StepUpContext, type Run } from "./stepUpContext.ts";

interface Pending {
  action: string;
  resource: string;
  resolve: (token: string) => void;
  reject: (reason: Error) => void;
}

/**
 * Asks for a fresh authenticator code right before a sensitive call. The token
 * goes straight into that one request; it is not kept in state or storage.
 */
export const StepUpProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [pending, setPending] = React.useState<Pending | null>(null);
  const [code, setCode] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [keyAvailable, setKeyAvailable] = React.useState(false);

  const run = React.useCallback<Run>(async (action, resource, operation) => {
    const [status, keys] = await Promise.all([fetchMfaStatus(), fetchSecurityKeyStatus()]);
    if (!status.required) return operation(null);
    if (!status.enrolled && !keys.enrolled) {
      throw new Error("Set up an authenticator or a passkey first, in Account security.");
    }
    setKeyAvailable(keys.enrolled);
    const token = await new Promise<string>((resolve, reject) => {
      setCode("");
      setError(null);
      setPending({ action, resource, resolve, reject });
    });
    return operation(token);
  }, []);

  const cancel = () => {
    pending?.reject(new StepUpCancelledError());
    setPending(null);
  };

  const useKey = async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      pending.resolve(await stepUpWithSecurityKey(pending.action, pending.resource));
      setPending(null);
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      pending.resolve(await requestStepUpToken(pending.action, pending.resource, code.trim()));
      setPending(null);
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setCode("");
      setBusy(false);
    }
  };

  return (
    <StepUpContext.Provider value={run}>
      {children}
      <Dialog open={pending !== null} title="Confirm with your authenticator" onClose={cancel} closeOnBackdrop={false}>
        <form onSubmit={submit} noValidate aria-label="Authenticator code">
          <p>Enter the current 6-digit code. It confirms this one action only.</p>
          <TextField label="Authenticator code" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={6} required />
          {error && <Alert tone="danger" live="assertive" title="Code not accepted" className="mb-3">{error}</Alert>}
          <div className="btn-list">
            <Button type="submit" loading={busy} disabled={code.trim().length !== 6}>Confirm</Button>
            {keyAvailable && <Button type="button" variant="secondary" loading={busy} onClick={useKey}>Use passkey or security key</Button>}
            <Button type="button" variant="ghost" onClick={cancel}>Cancel</Button>
          </div>
        </form>
      </Dialog>
    </StepUpContext.Provider>
  );
};
