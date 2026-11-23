import React from "react";
import { useParams } from "react-router-dom";
import { IconCheck, IconX } from "@tabler/icons-react";
import { decideRecoveryRequest, fetchGuardians, fetchRecoveryRequestById, type Guardian, type RecoveryRequest } from "../../api/recovery.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid } from "../../components/ui/Card.tsx";
import { Button, ButtonLink } from "../../components/ui/Button.tsx";
import { Checkbox } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { ConfirmDialog } from "../../components/ui/Dialog.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { RecoveryStateBadge } from "../../components/ui/StatusBadge.tsx";
import { ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { RecoveryProgress } from "../../components/ssi/RecoveryProgress.tsx";
import { useAuth } from "../../context/AuthContext.ts";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { findDeviceKey } from "../../lib/guardianDeviceKey.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";
import { assignmentsFor, isOpen } from "./guardianData.ts";

async function load(requestId: string, userId: string): Promise<{ request: RecoveryRequest; guardian: Guardian | null }> {
  const request = await fetchRecoveryRequestById(requestId);
  const guardians = await fetchGuardians(request.walletId);
  const [assignment] = assignmentsFor(userId, [request], guardians);
  return { request, guardian: assignment?.guardian ?? null };
}

export const ApproveRecoveryPage: React.FC = () => {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const data = useAsync(() => load(id, user?.id ?? ""), [id, user?.id]);
  const [confirmed, setConfirmed] = React.useState(false);
  const [decision, setDecision] = React.useState<"APPROVE" | "REJECT" | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [updated, setUpdated] = React.useState<RecoveryRequest | null>(null);
  const withStepUp = useStepUp();
  const crumbs = [{ label: "Guardian tasks", to: "/guardian" }, { label: "Review request" }];

  if (data.status === "loading") return <Page title="Review recovery request" breadcrumbs={crumbs}><div className="card"><LoadingState label="Loading request" /></div></Page>;
  if (data.status === "error") return <Page title="Review recovery request" breadcrumbs={crumbs}><div className="card"><ErrorState error={data.error} title="The request could not be loaded" onRetry={data.reload} /></div></Page>;

  const { guardian } = data.data;
  const request = updated ?? data.data.request;

  const onDecide = async () => {
    if (!decision || !guardian) return;
    setBusy(true);
    setError(null);
    try {
      const key = await findDeviceKey(user?.id ?? "");
      if (!key) throw new Error("This browser does not hold your Guardian key. Bind a new key on the Guardian tasks page.");
      setUpdated(await withStepUp("recovery.decide", request.requestId, (token) => decideRecoveryRequest(request, guardian, decision, key, token)));
      setDecision(null);
    } catch (cause) {
      setError(describeError(cause));
      setDecision(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page eyebrow="Guardian tasks" title="Review recovery request" breadcrumbs={crumbs} actions={<RecoveryStateBadge state={request.status} />}>
      {!guardian && (
        <Alert tone="warning" title="You are not an active guardian for this wallet">
          Decisions can only be recorded by a guardian registered by the wallet owner.
        </Alert>
      )}
      <Grid cols={2}>
        <Card title="Request">
          <DataGrid items={[
            { label: "Reason", value: humanize(request.reason) },
            { label: "Wallet", value: <IdentifierText value={request.walletId} label="wallet" /> },
            { label: "Requested", value: formatDateTime(request.createdAt) },
            { label: "Decisions close", value: formatDateTime(request.approvalExpiresAt) },
            { label: "Risk check", value: request.riskStatus === "ON_HOLD" ? `On hold (${humanize(request.riskLevel)})` : humanize(request.riskStatus) },
            guardian ? { label: "You act as", value: <>{guardian.displayName} · <IdentifierText value={guardian.guardianDid} label="guardian DID" copy={false} /></> } : null,
          ]} />
        </Card>
        <Card title="Progress"><RecoveryProgress request={request} /></Card>
      </Grid>

      {updated && <Alert tone="success" live="polite" title="Your decision was recorded" actions={<ButtonLink to="/guardian" size="sm" variant="secondary">Back to guardian tasks</ButtonLink>}>The recovery service verified your signed decision. Current state: {humanize(updated.status)}.</Alert>}
      {error && <Alert tone="danger" live="assertive" title="Decision not recorded">{error}</Alert>}

      {guardian && isOpen(request) && !updated && (
        <Card
          title="Your decision"
          subtitle="Signed in this browser with your own Guardian key. The platform cannot sign for you."
          footer={(
            <div className="btn-list">
              <Button onClick={() => setDecision("APPROVE")} disabled={!confirmed} icon={<IconCheck aria-hidden="true" />}>Approve</Button>
              <Button variant="danger" onClick={() => setDecision("REJECT")} icon={<IconX aria-hidden="true" />}>Reject</Button>
            </div>
          )}
        >
          <Alert tone="warning" className="mb-3">Confirm with the wallet owner through another channel before approving.</Alert>
          <Checkbox className="mb-0" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} label="I confirmed with the wallet owner outside this platform that they made this request." />
        </Card>
      )}

      <ConfirmDialog
        open={decision !== null}
        title={decision === "APPROVE" ? "Approve recovery?" : "Reject recovery?"}
        confirmLabel={decision === "APPROVE" ? "Sign and approve" : "Sign and reject"}
        confirmVariant={decision === "APPROVE" ? "primary" : "danger"}
        busy={busy}
        onConfirm={onDecide}
        onCancel={() => setDecision(null)}
      >
        <p className="mb-0">{decision === "APPROVE"
          ? "Approval counts toward the quorum. After enough approvals a time-lock starts, then the owner's managed key is rotated."
          : "Rejection is recorded and counts against this request."}</p>
      </ConfirmDialog>
    </Page>
  );
};
