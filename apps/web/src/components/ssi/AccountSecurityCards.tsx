import React from "react";
import { IconKey, IconLock } from "@tabler/icons-react";
import { changePassword, fetchSecurityKeyStatus, registerSecurityKey } from "../../api/stepUp.ts";
import { Card } from "../ui/Card.tsx";
import { Button } from "../ui/Button.tsx";
import { TextField } from "../ui/Field.tsx";
import { Alert } from "../ui/Alert.tsx";
import { Badge } from "../ui/StatusBadge.tsx";
import { ErrorState, LoadingState } from "../ui/States.tsx";
import { useStepUp } from "./stepUpContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { webAuthnAvailable } from "../../lib/webauthnClient.ts";
import { useAuth } from "../../context/AuthContext.ts";

/** A passkey or security key: phishing resistant, unlike an authenticator code. */
export const SecurityKeyCard: React.FC = () => {
  const status = useAsync(fetchSecurityKeyStatus, []);
  const [password, setPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  if (status.status === "loading") return <div className="card"><LoadingState label="Checking security keys" rows={2} /></div>;
  if (status.status === "error") return <div className="card"><ErrorState error={status.error} title="Security key status is unavailable" onRetry={status.reload} /></div>;
  const { configured, enrolled } = status.data;

  const onRegister = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await registerSecurityKey(password);
      status.reload();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setPassword("");
      setBusy(false);
    }
  };

  return (
    <Card
      title="Passkey or security key"
      subtitle="Resists phishing, so prefer it over authenticator codes where you can."
      actions={enrolled ? <Badge tone="success">Registered</Badge> : <Badge tone="neutral">Not registered</Badge>}
    >
      {!configured && <p className="mb-0">This deployment has no WebAuthn address configured, so security keys are not available.</p>}
      {configured && enrolled && <p className="mb-0">You can confirm sensitive actions with this key.</p>}
      {configured && !enrolled && (
        <form onSubmit={onRegister} noValidate aria-label="Register a security key">
          <TextField label="Password to add a key" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          {error && <Alert tone="danger" live="assertive" title="Key not registered" className="mb-3">{error}</Alert>}
          <Button type="submit" variant="secondary" loading={busy} disabled={!password || !webAuthnAvailable()} icon={<IconKey aria-hidden="true" />}>Register a key</Button>
        </form>
      )}
    </Card>
  );
};

export const PasswordCard: React.FC = () => {
  const { user } = useAuth();
  const withStepUp = useStepUp();
  const [current, setCurrent] = React.useState("");
  const [next, setNext] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await withStepUp("account.password.change", user?.id ?? "", (token) => changePassword(current, next, token));
      window.location.assign("/login");
    } catch (cause) {
      setError(describeError(cause));
      setBusy(false);
    } finally {
      setCurrent("");
      setNext("");
    }
  };

  return (
    <Card title="Password" subtitle="Changing it signs out every session, including this one.">
      <form onSubmit={onSubmit} noValidate aria-label="Change password">
        <TextField label="Current password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        <TextField label="New password" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} hint="At least 12 characters." required />
        {error && <Alert tone="danger" live="assertive" title="Password not changed" className="mb-3">{error}</Alert>}
        <Button type="submit" variant="secondary" loading={busy} disabled={!current || next.length < 15} icon={<IconLock aria-hidden="true" />}>Change password</Button>
      </form>
    </Card>
  );
};
