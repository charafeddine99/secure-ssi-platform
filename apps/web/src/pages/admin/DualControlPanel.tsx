import React from "react";
import {
  approveDualControl,
  fetchDualControl,
  fetchReadiness,
  requestDualControl,
  type DualControlOperation,
} from "../../api/platformBackup.ts";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { useAuth } from "../../context/AuthContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

/** What really blocks production right now, straight from the service. */
export const ReadinessCard: React.FC = () => {
  const report = useAsync(fetchReadiness, []);
  if (report.status === "loading") return <div className="card"><LoadingState label="Checking readiness" rows={2} /></div>;
  if (report.status === "error") return <div className="card"><ErrorState error={report.error} title="Readiness is unavailable" onRetry={report.reload} /></div>;
  const { blockers, warnings, environment, ready, details } = report.data;
  const findings = [...blockers, ...warnings];
  return (
    <Card
      title="Production readiness"
      subtitle={`Environment: ${environment}`}
      actions={findings.length === 0 && ready ? <Badge tone="success">Ready</Badge> : <Badge tone="danger">Not production ready</Badge>}
    >
      <DataGrid items={[
        { label: "Issuer keys", value: humanize(details.keyCustody?.issuer ?? "unknown") },
        { label: "Live KMS connection", value: humanize(details.keyCustody?.liveKms ?? "unknown") },
        { label: "Revocation ledger", value: `${humanize(details.ledger?.protection ?? "unknown")} · ${details.ledger?.sequence ?? 0} events` },
        { label: "Off-site copy", value: humanize(details.backup?.offsite ?? "unknown") },
        { label: "Immutable storage", value: humanize(details.backup?.immutable ?? "unknown") },
        { label: "Point-in-time recovery", value: humanize(details.backup?.pointInTime ?? "unknown") },
        { label: "Last verified restore point", value: formatDateTime(details.backup?.lastVerifiedRestorePoint ?? null) },
      ]} />
      {findings.length > 0 && (
        <Alert tone="warning" title="Open findings" className="mt-3">
          <ul className="mb-0 ps-3">{findings.map((code) => <li key={code}>{humanize(code)}</li>)}</ul>
        </Alert>
      )}
    </Card>
  );
};

/** Two distinct administrators for irreversible operations. The server enforces it. */
export const DualControlPanel: React.FC<{ backupId: string; targetDatabase: string }> = ({ backupId, targetDatabase }) => {
  const { user } = useAuth();
  const withStepUp = useStepUp();
  const operations = useAsync(fetchDualControl, []);
  const [reason, setReason] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [approved, setApproved] = React.useState<{ id: string; token: string } | null>(null);
  const target = `${backupId}:${targetDatabase}`;

  const onRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await withStepUp("dual-control.request", target, (token) => requestDualControl("PLATFORM_RESTORE", target, reason.trim(), token));
      setReason("");
      operations.reload();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };

  const onApprove = async (operation: DualControlOperation) => {
    setBusy(true);
    setError(null);
    try {
      const result = await withStepUp("dual-control.approve", operation.operationId, (token) => approveDualControl(operation.operationId, token));
      setApproved({ id: operation.operationId, token: result.executionToken });
      operations.reload();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Two-person approval" subtitle="A second administrator must approve. The restore then runs from the operator CLI with the one-time token.">
      <form onSubmit={onRequest} className="row g-3 align-items-end" noValidate aria-label="Request restore approval">
        <div className="col-md-8"><TextField groupClassName="mb-0" label="Reason for this restore" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} required /></div>
        <div className="col-md-auto"><Button type="submit" variant="secondary" loading={busy} disabled={reason.trim().length < 3}>Request approval</Button></div>
      </form>
      {error && <Alert tone="danger" live="assertive" title="Not completed" className="mt-3">{error}</Alert>}
      {approved && (
        <Alert tone="success" title="Approved" className="mt-3">
          One-time execution token for <code>{approved.id}</code>. It is shown once: <code data-testid="dual-control-token" className="user-select-all">{approved.token}</code>
        </Alert>
      )}
      {operations.status === "error" && <ErrorState error={operations.error} title="Approvals are unavailable" onRetry={operations.reload} />}
      {operations.status === "success" && operations.data.length === 0 && <EmptyState title="No approval requests" />}
      {operations.status === "success" && operations.data.length > 0 && (
        <div className="mt-3">
          <Table caption="Approval requests" inCard={false} stackBelow="md">
            <thead><tr><th scope="col">Operation</th><th scope="col">Requested by</th><th scope="col">Status</th><th scope="col">Expires</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>
              {operations.data.map((item) => (
                <tr key={item.operationId}>
                  <td data-label="Operation">{humanize(item.operationType)} <IdentifierText value={item.operationId} label="operation" copy={false} /></td>
                  <td data-label="Requested by"><IdentifierText value={item.requestedBy} label="administrator" copy={false} /></td>
                  <td data-label="Status"><Badge tone={item.status === "APPROVED" ? "success" : "neutral"}>{humanize(item.status)}</Badge></td>
                  <td data-label="Expires">{formatDateTime(item.expiresAt)}</td>
                  <td data-label="Actions">
                    {item.status === "PENDING" && item.requestedBy !== user?.id && <Button size="sm" loading={busy} onClick={() => onApprove(item)}>Approve</Button>}
                    {item.status === "PENDING" && item.requestedBy === user?.id && <span className="small text-secondary">Needs another administrator</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </Card>
  );
};
