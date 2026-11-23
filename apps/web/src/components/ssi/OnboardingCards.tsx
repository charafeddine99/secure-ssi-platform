import React from "react";
import { decideOnboarding, fetchOnboardingRequests, inviteAdministrator, type OnboardingItem } from "../../api/registration.ts";
import { Card } from "../ui/Card.tsx";
import { Alert } from "../ui/Alert.tsx";
import { Button } from "../ui/Button.tsx";
import { TextField } from "../ui/Field.tsx";
import { Badge } from "../ui/StatusBadge.tsx";
import { AsyncView } from "../ui/AsyncView.tsx";
import { EmptyState } from "../ui/States.tsx";
import { useStepUp } from "./stepUpContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

const Application: React.FC<{ item: OnboardingItem; onDone: () => void }> = ({ item, onDone }) => {
  const withStepUp = useStepUp();
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const decide = async (decision: "approve" | "reject") => {
    setBusy(true);
    setError(null);
    try {
      await withStepUp("onboarding.decide", item.requestId, (token) => decideOnboarding(item.requestId, decision, note.trim(), token));
      onDone();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <li className="list-group-item">
      <div className="d-flex flex-wrap justify-content-between gap-2 mb-2">
        <div>
          <div className="fw-medium">{item.organization}</div>
          <div className="small text-secondary text-break">{item.displayName} · {item.email} · {formatDateTime(item.createdAt)}</div>
        </div>
        <Badge tone="warning">{humanize(item.role)}</Badge>
      </div>
      <p className="text-secondary mb-2">{item.purpose}</p>
      {error && <Alert tone="danger" live="assertive" title="Not saved" className="mb-2">{error}</Alert>}
      <TextField label="Decision note" value={note} maxLength={500} hint="Say how the organisation was checked." onChange={(e) => setNote(e.target.value)} required />
      <div className="btn-list">
        <Button size="sm" loading={busy} disabled={note.trim().length < 3} onClick={() => decide("approve")}>Approve</Button>
        <Button size="sm" variant="danger" loading={busy} disabled={note.trim().length < 3} onClick={() => decide("reject")}>Reject</Button>
      </div>
    </li>
  );
};

export const OnboardingCard: React.FC<{ onChanged: () => void }> = ({ onChanged }) => {
  const requests = useAsync(fetchOnboardingRequests, []);
  const done = () => { requests.reload(); onChanged(); };
  return (
    <Card title="Applications" subtitle="Issuers and Verifiers wait here. After approving an Issuer, link it to a trusted institution below." flush>
      <AsyncView state={requests} onRetry={requests.reload} loadingLabel="Loading applications" errorTitle="Applications are unavailable">
        {(items) => items.length === 0 ? <EmptyState title="No applications waiting" /> : (
          <ul className="list-group list-group-flush">{items.map((item) => <Application key={item.requestId} item={item} onDone={done} />)}</ul>
        )}
      </AsyncView>
    </Card>
  );
};

export const InviteAdministratorCard: React.FC = () => {
  const withStepUp = useStepUp();
  const [email, setEmail] = React.useState("");
  const [link, setLink] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const invite = async () => {
    const address = email.trim().toLowerCase();
    setBusy(true);
    setError(null);
    setLink(null);
    try {
      const code = await withStepUp("admin.invite", address, (token) => inviteAdministrator(address, token));
      setLink(`${window.location.origin}/register?invite=${encodeURIComponent(code)}`);
      setEmail("");
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="Invite an administrator" subtitle="Administrators cannot sign up themselves. The link works once, for this address, for 24 hours.">
      {error && <Alert tone="danger" live="assertive" title="Invitation not created" className="mb-3">{error}</Alert>}
      {link && <Alert tone="success" live="polite" title="Send this link privately" className="mb-3"><span className="text-break">{link}</span></Alert>}
      <TextField label="Administrator e-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} />
      <Button variant="secondary" loading={busy} disabled={!email.includes("@")} onClick={invite}>Create invitation</Button>
    </Card>
  );
};
