import React from "react";
import {
  fetchRecoveryOversight,
  fetchRecoveryOversightCase,
  reviewRecoveryRisk,
  type RecoveryOversightCase,
  type RecoveryState,
} from "../../api/recovery.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { SelectField, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { RecoveryStateBadge } from "../../components/ui/StatusBadge.tsx";
import { RecoveryTimeline } from "../../components/ssi/RecoveryTimeline.tsx";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, formatDuration, humanize } from "../../lib/format.ts";

const FILTERS: Array<{ value: RecoveryState | ""; label: string }> = [
  { value: "", label: "All states" },
  { value: "PENDING_APPROVALS", label: "Waiting for guardians" },
  { value: "WAITING_TIMELOCK", label: "Time-lock running" },
  { value: "RECONCILIATION_REQUIRED", label: "Needs reconciliation" },
  { value: "COMPLETED", label: "Completed" },
  { value: "REJECTED", label: "Rejected" },
  { value: "CANCELLED", label: "Cancelled" },
  { value: "EXPIRED", label: "Expired" },
  { value: "FAILED", label: "Failed" },
];

export const RecoveryOversightPage: React.FC = () => {
  const [filter, setFilter] = React.useState<RecoveryState | "">("");
  const [selected, setSelected] = React.useState<string | null>(null);
  const cases = useAsync<RecoveryOversightCase[]>(() => fetchRecoveryOversight(filter || undefined), [filter]);

  return (
    <Page
      eyebrow="Administration"
      title="Recovery oversight"
      description="Guardian recovery cases across the platform."
      breadcrumbs={[{ label: "Administration", to: "/admin" }, { label: "Recovery oversight" }]}
    >
      <Alert tone="info" title="What an administrator can and cannot do">
        You can follow cases and review a risk hold. You cannot approve for a guardian or shorten the quorum
        or time-lock: releasing a hold only removes the hold. Guardian challenges are never shown here.
      </Alert>
      <Card
        title="Recovery cases"
        actions={(
          <div className="d-flex gap-2 align-items-end">
            <SelectField groupClassName="mb-0" label="State" value={filter} onChange={(e) => { setFilter(e.target.value as RecoveryState | ""); setSelected(null); }}>
              {FILTERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </SelectField>
            <Button variant="secondary" size="sm" onClick={cases.reload}>Refresh</Button>
          </div>
        )}
        flush
      >
        {cases.status === "loading" && <LoadingState label="Loading recovery cases" />}
        {cases.status === "error" && <ErrorState error={cases.error} title="The recovery service could not be reached" onRetry={cases.reload} />}
        {cases.status === "success" && cases.data.length === 0 && <EmptyState title="No recovery cases" description="No case matches this filter." />}
        {cases.status === "success" && cases.data.length > 0 && (
          <Table caption="Recovery cases" stackBelow="md">
            <thead><tr><th scope="col">Requested</th><th scope="col">Reason</th><th scope="col">State</th><th scope="col">Quorum</th><th scope="col">Time-lock</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>
              {cases.data.map((item) => (
                <tr key={item.requestId} className={selected === item.requestId ? "table-active" : undefined}>
                  <td data-label="Requested">{formatDateTime(item.createdAt)}</td>
                  <td data-label="Reason">{humanize(item.reason)}</td>
                  <td data-label="State"><RecoveryStateBadge state={item.state} />{item.riskStatus === "ON_HOLD" && <div className="small text-danger">Risk hold</div>}</td>
                  <td data-label="Quorum">{item.approvalCount} / {item.minimumApprovals} of {item.guardianCount}{item.rejectionCount ? ` · ${item.rejectionCount} rejected` : ""}</td>
                  <td data-label="Time-lock">{formatDuration(item.timeLockSeconds)}</td>
                  <td data-label="Actions"><Button size="sm" variant="secondary" onClick={() => setSelected(item.requestId)}>View</Button></td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      {selected && <CaseDetail requestId={selected} />}
    </Page>
  );
};

const CaseDetail: React.FC<{ requestId: string }> = ({ requestId }) => {
  const detail = useAsync(() => fetchRecoveryOversightCase(requestId), [requestId]);
  if (detail.status === "loading") return <div className="card"><LoadingState label="Loading case" /></div>;
  if (detail.status === "error") return <div className="card"><ErrorState error={detail.error} title="The case could not be loaded" onRetry={detail.reload} /></div>;
  const { case: item, timeline } = detail.data;
  return (
    <Card title="Case detail" subtitle={<IdentifierText value={item.requestId} label="request ID" />} actions={<RecoveryStateBadge state={item.state} />}>
      <div className="row g-4">
        <div className="col-lg-6">
          <DataGrid items={[
            { label: "Wallet", value: <IdentifierText value={item.walletId} label="wallet" copy={false} /> },
            { label: "Owner account", value: <IdentifierText value={item.ownerUserId} label="owner" copy={false} /> },
            { label: "Policy version", value: item.policyVersion },
            { label: "Risk result", value: `${humanize(item.riskLevel)} · ${humanize(item.riskStatus)}` },
            { label: "Approvals close", value: formatDateTime(item.approvalExpiresAt) },
            { label: "Executable after", value: item.executableAfter ? formatDateTime(item.executableAfter) : "After quorum" },
            { label: "Case expires", value: formatDateTime(item.expiresAt) },
            { label: "Execution attempts", value: item.attemptCount },
            item.failureCode ? { label: "Failure", value: humanize(item.failureCode) } : null,
            item.successorDid ? { label: "Successor DID", value: <IdentifierText value={item.successorDid} label="successor DID" /> } : null,
          ]} />
          {item.riskStatus === "ON_HOLD" && <RiskReview requestId={item.requestId} onDone={detail.reload} />}
          {item.state === "COMPLETED" && (
            <Alert tone="info" className="mt-3">
              The predecessor key was retired and a new managed key and DID were issued. No key was "recovered";
              credentials bound to the old DID may need re-issuance.
            </Alert>
          )}
        </div>
        <div className="col-lg-6">
          <h3 className="h4">Audit timeline</h3>
          <RecoveryTimeline events={timeline} />
        </div>
      </div>
    </Card>
  );
};

const RiskReview: React.FC<{ requestId: string; onDone: () => void }> = ({ requestId, onDone }) => {
  const withStepUp = useStepUp();
  const [reason, setReason] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const decide = async (decision: "RELEASE" | "UPHOLD") => {
    setBusy(true);
    setError(null);
    try {
      await withStepUp("recovery.risk.review", requestId, (token) => reviewRecoveryRisk(requestId, decision, reason.trim(), token));
      onDone();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mt-3">
      <Alert tone="warning" title="This key rotation is on hold" className="mb-3">
        Release only after checking with the wallet owner. Upholding the hold cancels the request. Neither replaces the guardians' quorum or the time-lock.
      </Alert>
      <TextField label="Review reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} required />
      {error && <Alert tone="danger" live="assertive" title="Review not recorded" className="mb-3">{error}</Alert>}
      <div className="btn-list">
        <Button size="sm" loading={busy} disabled={reason.trim().length < 3} onClick={() => decide("RELEASE")}>Release hold</Button>
        <Button size="sm" variant="danger" loading={busy} disabled={reason.trim().length < 3} onClick={() => decide("UPHOLD")}>Uphold and cancel</Button>
      </div>
    </div>
  );
};
