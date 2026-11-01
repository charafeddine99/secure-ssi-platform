import React from "react";
import { IconHistory, IconSearch, IconShieldOff } from "@tabler/icons-react";
import { fetchCredentialHistory, fetchCredentialStatus, revokeCredential, type CredentialStatusSnapshot } from "../../api/status.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { TextAreaField, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { ConfirmDialog } from "../../components/ui/Dialog.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { CredentialStatusBadge } from "../../components/ui/StatusBadge.tsx";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { useToast } from "../../components/ui/toastContext.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

export const RevocationRegistryPage: React.FC = () => {
  const toast = useToast();
  const [credentialId, setCredentialId] = React.useState("");
  const [snapshot, setSnapshot] = React.useState<CredentialStatusSnapshot | null>(null);
  const [lookupError, setLookupError] = React.useState<string | null>(null);
  const [looking, setLooking] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const [confirming, setConfirming] = React.useState(false);
  const [revoking, setRevoking] = React.useState(false);
  const [revokeError, setRevokeError] = React.useState<string | null>(null);

  const onLookup = async (event: React.FormEvent) => {
    event.preventDefault();
    const id = credentialId.trim();
    setLookupError(null);
    setRevokeError(null);
    setSnapshot(null);
    if (!id) { setLookupError("Enter the credential identifier (for example urn:uuid:…)."); return; }
    setLooking(true);
    try {
      setSnapshot(await fetchCredentialStatus(id));
    } catch (error) {
      setLookupError(describeError(error));
    } finally {
      setLooking(false);
    }
  };

  const onRevoke = async () => {
    if (!snapshot) return;
    setRevoking(true);
    setRevokeError(null);
    try {
      const updated = await revokeCredential(snapshot.credentialId, reason.trim());
      setSnapshot(updated);
      setReason("");
      toast("success", "Credential revoked. Verifiers checking the status list will now reject it.");
    } catch (error) {
      setRevokeError(describeError(error));
    } finally {
      setRevoking(false);
      setConfirming(false);
    }
  };

  return (
    <Page
      eyebrow="Issuer workspace"
      title="Status and revocation"
      description="Check or revoke a credential you issued."
      breadcrumbs={[{ label: "Issuer", to: "/issuer" }, { label: "Status and revocation" }]}
      narrow
    >
      <Card title="Find a credential">
        <form className="row g-2 align-items-start" onSubmit={onLookup} noValidate>
          <div className="col-md">
            <TextField groupClassName="mb-0" label="Credential ID" value={credentialId} onChange={(e) => setCredentialId(e.target.value)} spellCheck={false} autoComplete="off" error={lookupError} className="font-monospace" />
          </div>
          <div className="col-md-auto pt-md-4 mt-md-1">
            <Button type="submit" loading={looking} icon={<IconSearch aria-hidden="true" />}>Check status</Button>
          </div>
        </form>
      </Card>

      {snapshot && (
        <Card title="Current status" actions={<CredentialStatusBadge status={snapshot.status} />} status={snapshot.revoked ? "danger" : undefined}>
          <DataGrid items={[
            { label: "Credential ID", value: <IdentifierText value={snapshot.credentialId} label="credential ID" /> },
            { label: "Revoked", value: snapshot.revoked ? `Yes, ${formatDateTime(snapshot.revokedAt)}` : "No" },
            snapshot.revocationReason ? { label: "Reason", value: snapshot.revocationReason } : null,
          ]} />
          {!snapshot.revoked && (
            <div className="border-top mt-4 pt-4">
              <TextAreaField label="Revocation reason" hint="Recorded in the audit log. Do not include personal data." rows={3} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} required />
              {revokeError && <Alert tone="danger" live="assertive" title="Not revoked" className="mb-3">{revokeError}</Alert>}
              <Button variant="danger" onClick={() => setConfirming(true)} disabled={reason.trim().length < 3} icon={<IconShieldOff aria-hidden="true" />}>Revoke credential</Button>
            </div>
          )}
        </Card>
      )}

      {snapshot && <StatusHistory credentialId={snapshot.credentialId} status={snapshot.status} />}

      <ConfirmDialog open={confirming} title="Revoke this credential?" confirmLabel="Revoke permanently" confirmVariant="danger" busy={revoking} onConfirm={onRevoke} onCancel={() => setConfirming(false)}>
        <p className="mb-0">Revocation cannot be undone. The holder keeps the signed credential, but verifiers will reject it after checking its status.</p>
      </ConfirmDialog>
    </Page>
  );
};

/** Append-only lifecycle events recorded by the Identity Service for this credential. */
const StatusHistory: React.FC<{ credentialId: string; status: string }> = ({ credentialId, status }) => {
  // Reload after a revocation so the new event appears.
  const history = useAsync(() => fetchCredentialHistory(credentialId), [credentialId, status]);
  return (
    <Card title="Status history" subtitle="Recorded by the Identity Service. Visible to the issuing authority only." flush>
      {history.status === "loading" && <LoadingState label="Loading status history" />}
      {history.status === "error" && <ErrorState error={history.error} title="Status history is unavailable" onRetry={history.reload} />}
      {history.status === "success" && history.data.events.length === 0 && (
        <EmptyState icon={<IconHistory size={32} aria-hidden="true" />} title="No recorded events" description="The service returned no lifecycle events for this credential." />
      )}
      {history.status === "success" && history.data.events.length > 0 && (
        <ul className="list-group list-group-flush" aria-label="Credential status events, oldest first">
          {history.data.events.map((event) => {
            const recorded = typeof event.metadata.status === "string" ? event.metadata.status : null;
            return (
              <li key={event.eventId} className="list-group-item d-flex flex-wrap justify-content-between gap-2">
                <span className="fw-medium">{humanize(event.eventType).replace(/\bVc\b/g, "VC")}{recorded ? <span className="text-secondary fw-normal"> · {humanize(recorded)}</span> : null}</span>
                <time className="text-secondary" dateTime={event.createdAt}>{formatDateTime(event.createdAt)}</time>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
};
