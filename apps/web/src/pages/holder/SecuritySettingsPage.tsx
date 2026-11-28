import React from "react";
import { IconKey, IconTrash, IconUserPlus } from "@tabler/icons-react";
import {
  ACTIVE_RECOVERY_STATES,
  addGuardian,
  cancelRecoveryRequest,
  canInitiateRecovery,
  fetchGuardians,
  fetchRecoveryPolicyStrict,
  fetchRecoveryRequests,
  fetchRecoveryTimeline,
  initiateRecoveryRequest,
  removeGuardian,
  upsertRecoveryPolicy,
  type Guardian,
  type RecoveryPolicy,
  type RecoveryReason,
  type RecoveryRequest,
} from "../../api/recovery.ts";
import type { HolderWallet } from "../../api/wallet.ts";
import { fetchWalletKeys, type WalletKey } from "../../api/keys.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Checkbox, SelectField, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { ConfirmDialog } from "../../components/ui/Dialog.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { Badge, RecoveryStateBadge } from "../../components/ui/StatusBadge.tsx";
import type { BadgeTone } from "../../components/ui/tones.ts";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useToast } from "../../components/ui/toastContext.ts";
import { RecoveryProgress } from "../../components/ssi/RecoveryProgress.tsx";
import { RecoveryTimeline } from "../../components/ssi/RecoveryTimeline.tsx";
import { RecoveryNotificationsCard } from "../../components/ssi/RecoveryNotificationsCard.tsx";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, formatDuration, humanize } from "../../lib/format.ts";
import { useHolderWallet } from "./useHolderWallet.ts";
import { toForm, validatePolicyForm, type PolicyForm } from "./recoveryPolicyForm.ts";

interface RecoveryData {
  policy: RecoveryPolicy | null;
  guardians: Guardian[];
  requests: RecoveryRequest[];
}

async function loadRecovery(walletId: string): Promise<RecoveryData> {
  const [policy, guardians, requests] = await Promise.all([
    fetchRecoveryPolicyStrict(walletId),
    fetchGuardians(walletId),
    fetchRecoveryRequests(20),
  ]);
  return {
    policy,
    guardians: guardians.filter((guardian) => guardian.walletId === walletId),
    requests: requests.filter((request) => request.walletId === walletId),
  };
}

export const SecuritySettingsPage: React.FC = () => {
  const wallet = useHolderWallet();
  return (
    <Page
      eyebrow="Holder wallet"
      title="Recovery and security"
      description="Guardians and recovery rules for your wallet."
      breadcrumbs={[{ label: "Wallet", to: "/wallet" }, { label: "Recovery and security" }]}
    >
      <Alert tone="info" title="What wallet key recovery does">
        <ul className="mb-0 ps-3">
          <li>Your wallet key is held by the platform. A completed recovery replaces it with a new key and DID, and signs out every session.</li>
          <li>You must be able to sign in to start. If you cannot sign in at all, this page cannot help: full account recovery is not available yet.</li>
          <li>Credentials issued to your old DID need re-issuing by their issuers. Recovery does not move them.</li>
        </ul>
      </Alert>
      {wallet.status === "loading" && <div className="card"><LoadingState label="Opening your wallet" /></div>}
      {wallet.status === "error" && <div className="card"><ErrorState error={wallet.error} title="Your wallet could not be opened" onRetry={wallet.reload} /></div>}
      {wallet.status === "success" && <WalletKeysCard walletId={wallet.data.walletId} />}
      {wallet.status === "success" && <RecoverySettings wallet={wallet.data} />}
      <RecoveryNotificationsCard />
    </Page>
  );
};

const RecoverySettings: React.FC<{ wallet: HolderWallet }> = ({ wallet }) => {
  const toast = useToast();
  const data = useAsync(() => loadRecovery(wallet.walletId), [wallet.walletId]);

  if (data.status === "loading") return <div className="card"><LoadingState label="Loading recovery configuration" /></div>;
  if (data.status === "error") return <div className="card"><ErrorState error={data.error} title="The recovery service could not be reached" onRetry={data.reload} /></div>;

  const { policy, guardians, requests } = data.data;
  const activeGuardians = guardians.filter((guardian) => guardian.status === "ACTIVE");
  const activeRequest = requests.find((request) => ACTIVE_RECOVERY_STATES.includes(request.status)) ?? null;
  const latestClosed = activeRequest ? null : requests.find((request) => !ACTIVE_RECOVERY_STATES.includes(request.status)) ?? null;

  return (
    <>
      {activeRequest && <ActiveRecovery request={activeRequest} policy={policy} onChanged={() => { data.reload(); }} />}
      {latestClosed && <LatestRecovery request={latestClosed} />}
      <Grid cols={2}>
        <PolicyCard walletId={wallet.walletId} policy={policy} onSaved={() => { toast("success", "Recovery policy saved."); data.reload(); }} />
        <GuardiansCard walletId={wallet.walletId} guardians={guardians} policy={policy} onChanged={data.reload} />
      </Grid>
      {!activeRequest && (
        <StartRecovery
          walletId={wallet.walletId}
          policy={policy}
          activeGuardianCount={activeGuardians.length}
          onStarted={() => { toast("success", "Recovery requested. Your guardians can now respond."); data.reload(); }}
        />
      )}
      <Card title="Recovery history" flush>
        {requests.length === 0 ? <EmptyState title="No recovery requests" /> : (
          <Table caption="Recovery requests">
            <thead><tr><th scope="col">Requested</th><th scope="col">Reason</th><th scope="col">State</th><th scope="col">Approvals</th></tr></thead>
            <tbody>
              {requests.map((request) => (
                <tr key={request.requestId}>
                  <td data-label="Requested">{formatDateTime(request.createdAt)}</td>
                  <td data-label="Reason">{humanize(request.reason)}</td>
                  <td data-label="State"><RecoveryStateBadge state={request.status} /></td>
                  <td data-label="Approvals">{request.approvalsCount ?? "?"} / {request.requiredCount ?? "?"}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
};

const PolicyCard: React.FC<{ walletId: string; policy: RecoveryPolicy | null; onSaved: () => void }> = ({ walletId, policy, onSaved }) => {
  const [form, setForm] = React.useState<PolicyForm>(() => toForm(policy));
  const [errors, setErrors] = React.useState<Partial<Record<keyof PolicyForm, string>>>({});
  const [saving, setSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState<string | null>(null);
  const withStepUp = useStepUp();
  const set = (key: keyof PolicyForm) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [key]: key === "allowCancellation" ? event.target.checked : event.target.value }));

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const result = validatePolicyForm(form, walletId);
    setErrors(result.errors);
    setSaveError(null);
    if (!result.policy) return;
    setSaving(true);
    try {
      const next = result.policy;
      await withStepUp("recovery.policy.update", walletId, (token) => upsertRecoveryPolicy(next, token));
      onSaved();
    } catch (error) {
      setSaveError(describeError(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card
      title="Recovery policy"
      subtitle={policy ? `Version ${policy.version ?? 1}. Changes apply to future recovery requests.` : "No policy yet. Recovery cannot start until you save one."}
      actions={policy ? <Badge tone="success">Configured</Badge> : <Badge tone="warning">Not configured</Badge>}
    >
      {policy?.pendingEffectiveAt && (
        <Alert tone="warning" title="A weaker policy is scheduled" className="mb-3">
          It takes effect on {formatDateTime(policy.pendingEffectiveAt)}. The current rules stay in force until then, and your guardians were told.
        </Alert>
      )}
      <form onSubmit={onSubmit} noValidate>
        <div className="row">
          <TextField groupClassName="col-sm-6 mb-3" label="Required approvals (M)" type="number" min={2} max={32} value={form.minimumApprovals} onChange={set("minimumApprovals")} error={errors.minimumApprovals} required />
          <TextField groupClassName="col-sm-6 mb-3" label="Maximum guardians (N)" type="number" min={1} max={32} value={form.maximumGuardians} onChange={set("maximumGuardians")} error={errors.maximumGuardians} required />
          <TextField groupClassName="col-sm-6 mb-3" label="Approval window (hours)" type="number" min={0} step="any" value={form.approvalWindowHours} onChange={set("approvalWindowHours")} error={errors.approvalWindowHours} required />
          <TextField groupClassName="col-sm-6 mb-3" label="Time-lock after quorum (hours)" type="number" min={0} step="any" value={form.timeLockHours} onChange={set("timeLockHours")} error={errors.timeLockHours} required />
          <TextField groupClassName="col-sm-6 mb-3" label="Request expires after (hours)" type="number" min={0} step="any" value={form.expirationHours} onChange={set("expirationHours")} error={errors.expirationHours} required />
          <TextField groupClassName="col-sm-6 mb-3" label="Attempts before cooldown" type="number" min={1} max={20} value={form.maximumAttempts} onChange={set("maximumAttempts")} error={errors.maximumAttempts} required />
          <TextField groupClassName="col-sm-6 mb-3" label="Cooldown (hours)" type="number" min={0} step="any" value={form.cooldownHours} onChange={set("cooldownHours")} error={errors.cooldownHours} required />
        </div>
        <Checkbox className="mb-3" checked={form.allowCancellation} onChange={set("allowCancellation")} label="Allow me to cancel a recovery request before it completes" />
        {saveError && <Alert tone="danger" live="assertive" title="Policy not saved" className="mb-3">{saveError}</Alert>}
        <Button type="submit" loading={saving}>Save policy</Button>
      </form>
    </Card>
  );
};

const GuardiansCard: React.FC<{ walletId: string; guardians: Guardian[]; policy: RecoveryPolicy | null; onChanged: () => void }> = ({
  walletId, guardians, policy, onChanged,
}) => {
  const toast = useToast();
  const [name, setName] = React.useState("");
  const [userId, setUserId] = React.useState("");
  const withStepUp = useStepUp();
  const [adding, setAdding] = React.useState(false);
  const [addError, setAddError] = React.useState<string | null>(null);
  const [toRemove, setToRemove] = React.useState<Guardian | null>(null);
  const [removing, setRemoving] = React.useState(false);
  const active = guardians.filter((guardian) => guardian.status === "ACTIVE");
  const listed = guardians.filter((guardian) => guardian.status !== "REMOVED");
  const atLimit = policy !== null && listed.length >= policy.maximumGuardians;

  const onAdd = async (event: React.FormEvent) => {
    event.preventDefault();
    setAddError(null);
    if (!name.trim() || !userId.trim()) {
      setAddError("Enter the guardian's name and account ID.");
      return;
    }
    setAdding(true);
    try {
      await withStepUp("recovery.guardian.manage", walletId, (token) => addGuardian({ walletId, guardianUserId: userId, displayName: name }, token));
      setName(""); setUserId("");
      toast("success", "Invitation sent. They must accept it with their own key.");
      onChanged();
    } catch (error) {
      setAddError(describeError(error));
    } finally {
      setAdding(false);
    }
  };

  const onRemove = async () => {
    if (!toRemove) return;
    setRemoving(true);
    try {
      const guardianId = toRemove.guardianId;
      const removed = await withStepUp("recovery.guardian.manage", guardianId, (token) => removeGuardian(guardianId, token));
      toast("success", removed.pendingEffectiveAt ? `Removal scheduled for ${formatDateTime(removed.pendingEffectiveAt)}.` : "Guardian removed.");
      setToRemove(null);
      onChanged();
    } catch (error) {
      toast("danger", describeError(error));
    } finally {
      setRemoving(false);
    }
  };

  return (
    <Card title="Guardians" subtitle={`${active.length} active${policy ? ` of at most ${policy.maximumGuardians}` : ""}. Each guardian needs their own account and accepts with a key only they hold.`} flush>
      {listed.length === 0 ? <EmptyState title="No guardians yet" description="Invite people you trust." /> : (
        <ul className="list-group list-group-flush" aria-label="Guardians">
          {listed.map((guardian) => (
            <li key={guardian.guardianId} className="list-group-item">
              <div className="row align-items-center g-3">
                <div className="col-auto"><span className="avatar avatar-sm bg-secondary-lt" aria-hidden="true">{guardian.displayName.slice(0, 1).toUpperCase()}</span></div>
                <div className="col min-w-0">
                  <div className="fw-medium">{guardian.displayName} <Badge tone={guardian.status === "ACTIVE" ? "success" : "warning"}>{humanize(guardian.status)}</Badge></div>
                  <div className="small text-secondary">
                    {guardian.guardianDid ? <IdentifierText value={guardian.guardianDid} label="guardian DID" copy={false} /> : "Waiting for them to accept"}
                    {" · "}invited {formatDateTime(guardian.createdAt)}
                    {guardian.pendingEffectiveAt && ` · change takes effect ${formatDateTime(guardian.pendingEffectiveAt)}`}
                  </div>
                </div>
                <div className="col-auto">
                  <Button variant="ghost" size="sm" onClick={() => setToRemove(guardian)} icon={<IconTrash aria-hidden="true" />}>
                    Remove<span className="visually-hidden"> {guardian.displayName}</span>
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form className="card-body border-top" onSubmit={onAdd} noValidate aria-label="Add a guardian">
        <h3 className="card-title mb-3">Invite a guardian</h3>
        <TextField label="Display name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required autoComplete="off" />
        <TextField label="Guardian account ID" value={userId} onChange={(e) => setUserId(e.target.value)} required autoComplete="off" spellCheck={false} />
        {addError && <Alert tone="danger" live="assertive" title="Guardian not added" className="mb-3">{addError}</Alert>}
        {atLimit && <Alert tone="warning" className="mb-3">Your policy allows no more guardians. Raise the maximum first.</Alert>}
        <Button type="submit" variant="secondary" loading={adding} disabled={atLimit} icon={<IconUserPlus aria-hidden="true" />}>Send invitation</Button>
      </form>
      <ConfirmDialog
        open={toRemove !== null}
        title="Remove guardian?"
        confirmLabel="Remove guardian"
        confirmVariant="danger"
        busy={removing}
        onConfirm={onRemove}
        onCancel={() => setToRemove(null)}
      >
        <p>{toRemove?.displayName} will no longer be able to approve recovery for this wallet. Once recovery is set up, removal waits out a delay and your guardians are told. It is refused while a recovery request is active.</p>
      </ConfirmDialog>
    </Card>
  );
};

const REASONS: Array<{ value: RecoveryReason; label: string }> = [
  { value: "LOST_ACCESS", label: "I can sign in, but I no longer trust or reach my wallet key" },
  { value: "DEVICE_LOSS", label: "A device I use was lost or stolen" },
  { value: "KEY_LOSS", label: "My key is no longer usable" },
  { value: "ACCOUNT_COMPROMISE", label: "I believe my account was compromised" },
];

const StartRecovery: React.FC<{ walletId: string; policy: RecoveryPolicy | null; activeGuardianCount: number; onStarted: () => void }> = ({
  walletId, policy, activeGuardianCount, onStarted,
}) => {
  const [reason, setReason] = React.useState<RecoveryReason>("LOST_ACCESS");
  const [confirming, setConfirming] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const withStepUp = useStepUp();
  const allowed = canInitiateRecovery(walletId, policy, activeGuardianCount, false);
  const blocker = !policy
    ? "Save a recovery policy first."
    : activeGuardianCount < policy.minimumApprovals
      ? `You need at least ${policy.minimumApprovals} active guardian${policy.minimumApprovals === 1 ? "" : "s"}; you have ${activeGuardianCount}.`
      : activeGuardianCount > policy.maximumGuardians
        ? "You have more active guardians than the policy allows."
        : null;

  const onConfirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await withStepUp("recovery.request.create", walletId, (token) => initiateRecoveryRequest({ walletId, reason }, token));
      setConfirming(false);
      onStarted();
    } catch (err) {
      setError(describeError(err));
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Start wallet key recovery" subtitle="Replaces your wallet key. You must be signed in to start." status="danger">
      <div className="row g-3 align-items-end">
        <div className="col-md-6">
          <SelectField groupClassName="mb-0" label="Reason" value={reason} onChange={(e) => setReason(e.target.value as RecoveryReason)}>
            {REASONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </SelectField>
        </div>
        <div className="col-md-auto">
          <Button variant="danger" onClick={() => setConfirming(true)} disabled={!allowed} icon={<IconKey aria-hidden="true" />}>Request recovery</Button>
        </div>
      </div>
      {(blocker || error) && (
        <div className="vstack gap-3 mt-3">
          {blocker && <Alert tone="warning">{blocker}</Alert>}
          {error && <Alert tone="danger" live="assertive" title="Recovery not started">{error}</Alert>}
        </div>
      )}
      <ConfirmDialog open={confirming} title="Request wallet recovery?" confirmLabel="Request recovery" confirmVariant="danger" busy={busy} onConfirm={onConfirm} onCancel={() => setConfirming(false)}>
        <p>Your guardians will be asked to approve. If {policy?.minimumApprovals ?? "the required number of"} approve, a time-lock of {formatDuration(policy?.timeLockSeconds ?? 0)} starts before the managed key is rotated. A risk check can also hold the rotation for human review. Completing recovery signs out all your sessions.</p>
      </ConfirmDialog>
    </Card>
  );
};

const ActiveRecovery: React.FC<{ request: RecoveryRequest; policy: RecoveryPolicy | null; onChanged: () => void }> = ({ request, policy, onChanged }) => {
  const toast = useToast();
  const [confirming, setConfirming] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const canCancel = policy?.allowCancellation !== false && request.status !== "EXECUTING";

  const onCancel = async () => {
    setBusy(true);
    try {
      await cancelRecoveryRequest(request.requestId);
      toast("success", "Recovery request cancelled.");
      setConfirming(false);
      onChanged();
    } catch (error) {
      toast("danger", describeError(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Recovery in progress"
      subtitle={`Requested ${formatDateTime(request.createdAt)} · approvals close ${formatDateTime(request.approvalExpiresAt)}`}
      actions={<RecoveryStateBadge state={request.status} />}
    >
      {request.riskStatus === "ON_HOLD" && (
        <Alert tone="warning" title="On hold for review" className="mb-3">
          The risk check returned {humanize(request.riskLevel)}. The key will not rotate until a reviewer releases this request, even if your guardians approve.
        </Alert>
      )}
      <div className="row g-4">
        <div className="col-lg-6"><RecoveryProgress request={request} /></div>
        <div className="col-lg-6"><TimelinePanel requestId={request.requestId} version={`${request.status}:${request.approvalsCount}`} /></div>
      </div>
      <div className="btn-list mt-4">
        <Button variant="secondary" size="sm" onClick={onChanged}>Refresh</Button>
        {canCancel && <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>Cancel request</Button>}
      </div>
      <ConfirmDialog open={confirming} title="Cancel recovery?" confirmLabel="Cancel recovery" confirmVariant="danger" busy={busy} onConfirm={onCancel} onCancel={() => setConfirming(false)}>
        <p>Guardian approvals collected so far will be discarded. Starting again counts as a new attempt.</p>
      </ConfirmDialog>
    </Card>
  );
};

const TimelinePanel: React.FC<{ requestId: string; version: string }> = ({ requestId, version }) => {
  const events = useAsync(() => fetchRecoveryTimeline(requestId), [requestId, version]);
  return (
    <>
      <h3 className="h4">Timeline</h3>
      {events.status === "loading" && <LoadingState label="Loading timeline" rows={2} />}
      {events.status === "error" && <ErrorState error={events.error} title="The timeline is unavailable" onRetry={events.reload} />}
      {events.status === "success" && <RecoveryTimeline events={events.data} />}
    </>
  );
};

const CLOSED_TEXT: Record<string, string> = {
  REJECTED: "Your guardians rejected this request. No key was changed.",
  CANCELLED: "This request was cancelled. No key was changed.",
  EXPIRED: "This request expired before it could complete. No key was changed.",
  FAILED: "Key rotation failed and was not applied. You can start a new request.",
};

/** The most recent finished request: success shows the rotation, never a "recovered" key. */
const LatestRecovery: React.FC<{ request: RecoveryRequest }> = ({ request }) => (
  <Card
    title="Latest recovery request"
    subtitle={`Requested ${formatDateTime(request.createdAt)}`}
    actions={<RecoveryStateBadge state={request.status} />}
    status={request.status === "COMPLETED" ? "success" : "secondary"}
  >
    <div className="row g-4">
      <div className="col-lg-6">
        {request.status === "COMPLETED" && request.result ? (
          <>
            <Alert tone="success" className="mb-3" title="Your wallet now uses a new key">
              The old key was retired, not recovered. A new managed key and DID were issued on {formatDateTime(request.result.completedAt)}.
              Credentials issued to the old DID stay verifiable as issued, but may need to be re-issued to the new DID.
            </Alert>
            <DataGrid items={[
              { label: "New DID", value: <IdentifierText value={request.result.successorDid} label="new DID" /> },
              { label: "Previous DID", value: <IdentifierText value={request.result.predecessorDid} label="previous DID" copy={false} /> },
            ]} />
          </>
        ) : (
          <Alert tone="info">{CLOSED_TEXT[request.status] ?? "This request is closed."}</Alert>
        )}
      </div>
      <div className="col-lg-6"><TimelinePanel requestId={request.requestId} version={request.status} /></div>
    </div>
  </Card>
);

// Mirrors ManagedKeyState in services/identity-service/app/domain/managed_key.py.
const KEY_STATE_TONE: Record<string, BadgeTone> = {
  PENDING: "info",
  ACTIVE: "success",
  ROTATING: "info",
  SUSPENDED: "warning",
  COMPROMISED: "danger",
  REVOKED: "danger",
  DESTROY_PENDING: "warning",
  DESTROYED: "neutral",
  FAILED: "danger",
};

/** Read-only view of the wallet's signing keys. A compromised key can only be replaced through recovery. */
const WalletKeysCard: React.FC<{ walletId: string }> = ({ walletId }) => {
  const keys = useAsync<WalletKey[]>(() => fetchWalletKeys(walletId), [walletId]);
  return (
    <Card title="Wallet keys" subtitle="Public key information only. The private key stays with the platform's key custody." flush>
      {keys.status === "loading" && <LoadingState label="Loading wallet keys" />}
      {keys.status === "error" && <ErrorState error={keys.error} title="Wallet keys are unavailable" onRetry={keys.reload} />}
      {keys.status === "success" && keys.data.length === 0 && (
        <EmptyState icon={<IconKey size={32} aria-hidden="true" />} title="No managed keys" description="The key service returned no keys for this wallet." />
      )}
      {keys.status === "success" && keys.data.length > 0 && (
        <Table caption="Wallet keys" stackBelow="md">
          <thead><tr><th scope="col">Fingerprint</th><th scope="col">Algorithm</th><th scope="col">Purpose</th><th scope="col">Version</th><th scope="col">State</th><th scope="col">Created</th></tr></thead>
          <tbody>
            {keys.data.map((key) => (
              <tr key={key.keyId}>
                <td data-label="Fingerprint">{key.fingerprint ? <IdentifierText value={key.fingerprint} label="key fingerprint" /> : <span className="text-secondary">Not reported</span>}</td>
                <td data-label="Algorithm">{key.algorithm}</td>
                <td data-label="Purpose">{humanize(key.purpose)}</td>
                <td data-label="Version">{key.keyVersion}</td>
                <td data-label="State"><Badge tone={KEY_STATE_TONE[key.state.toUpperCase()] ?? "neutral"}>{humanize(key.state)}</Badge></td>
                <td data-label="Created">{formatDateTime(key.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
};
