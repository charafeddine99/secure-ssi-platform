import React from "react";
import { IconShieldLock } from "@tabler/icons-react";
import { beginTotpEnrollment, confirmTotpEnrollment, fetchMfaStatus } from "../../api/stepUp.ts";
import { Card } from "../ui/Card.tsx";
import { Button } from "../ui/Button.tsx";
import { TextField } from "../ui/Field.tsx";
import { Alert } from "../ui/Alert.tsx";
import { Badge } from "../ui/StatusBadge.tsx";
import { ErrorState, LoadingState } from "../ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";

/** Authenticator-app setup. The secret is shown once and never stored here. */
export const AuthenticatorCard: React.FC = () => {
  const status = useAsync(fetchMfaStatus, []);
  const [password, setPassword] = React.useState("");
  const [secret, setSecret] = React.useState<string | null>(null);
  const [code, setCode] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const begin = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setSecret((await beginTotpEnrollment(password)).secret);
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setPassword("");
      setBusy(false);
    }
  };

  const confirm = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await confirmTotpEnrollment(code.trim());
      setSecret(null);
      status.reload();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setCode("");
      setBusy(false);
    }
  };

  if (status.status === "loading") return <div className="card"><LoadingState label="Checking your authenticator" /></div>;
  if (status.status === "error") return <div className="card"><ErrorState error={status.error} title="Authenticator status is unavailable" onRetry={status.reload} /></div>;
  const enrolled = status.data.enrolled;

  return (
    <Card
      title="Authenticator"
      subtitle="A second factor, asked for again before each sensitive action."
      actions={enrolled ? <Badge tone="success">Set up</Badge> : <Badge tone="warning">Not set up</Badge>}
    >
      {enrolled && <p className="mb-0">Your authenticator app is active. Guardian actions, recovery, key rotation and backups ask for a fresh code.</p>}
      {!enrolled && !secret && (
        <form onSubmit={begin} noValidate aria-label="Start authenticator setup">
          {status.data.required && <Alert tone="warning" className="mb-3">This deployment requires an authenticator for sensitive actions.</Alert>}
          <TextField label="Your account password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} hint="Needed so that an open session alone cannot add an authenticator." required />
          {error && <Alert tone="danger" live="assertive" title="Setup not started" className="mb-3">{error}</Alert>}
          <Button type="submit" variant="secondary" loading={busy} disabled={!password} icon={<IconShieldLock aria-hidden="true" />}>Set up authenticator</Button>
        </form>
      )}
      {!enrolled && secret && (
        <form onSubmit={confirm} noValidate aria-label="Confirm authenticator">
          <p>Add this key to your authenticator app, then enter the 6-digit code it shows. It is displayed only once.</p>
          <p><code data-testid="totp-secret" className="user-select-all">{secret}</code></p>
          <TextField label="Authenticator code" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={6} required />
          {error && <Alert tone="danger" live="assertive" title="Code not accepted" className="mb-3">{error}</Alert>}
          <Button type="submit" loading={busy} disabled={code.trim().length !== 6}>Confirm authenticator</Button>
        </form>
      )}
    </Card>
  );
};
