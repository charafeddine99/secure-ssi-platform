import React from "react";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { IconDatabaseExport, IconShieldCheck } from "@tabler/icons-react";
import {
  createPlatformBackup,
  fetchPlatformBackups,
  previewPlatformRestore,
  verifyPlatformBackup,
  type PlatformBackup,
  type PlatformBackupList,
  type PlatformRestorePreview,
} from "../../api/platformBackup.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { ConfirmDialog } from "../../components/ui/Dialog.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import type { BadgeTone } from "../../components/ui/tones.ts";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useToast } from "../../components/ui/toastContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, formatDuration, humanize } from "../../lib/format.ts";
import { DualControlPanel, ReadinessCard } from "./DualControlPanel.tsx";

const STATUS_TONE: Record<string, BadgeTone> = { SUCCEEDED: "success", RUNNING: "info", FAILED: "danger", EXPIRED: "neutral" };

function bytes(value: number | null): string {
  if (value === null) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1024 / 1024).toFixed(1)} MiB`;
}

export const PlatformBackupPage: React.FC = () => {
  const data = useAsync<PlatformBackupList>(() => fetchPlatformBackups(), []);
  const [previewing, setPreviewing] = React.useState<PlatformBackup | null>(null);
  return (
    <Page
      eyebrow="Administration"
      title="Platform backup & recovery"
      description="Encrypted backups of the identity, recovery and revocation data, and isolated restore drills."
      breadcrumbs={[{ label: "Administration", to: "/admin" }, { label: "Platform backup" }]}
    >
      <Alert tone="warning" title="This is not a wallet restore">
        A platform backup copies the identity, recovery and revocation data for disaster recovery. Holders
        restore their own credentials from their wallet. Restores go only into separate, empty drill
        databases and need a second administrator; the live database is never a target and no live cutover
        is automated. All sessions end after a restore.
      </Alert>
      <ReadinessCard />
      {data.status === "loading" && <div className="card"><LoadingState label="Loading backup jobs" /></div>}
      {data.status === "error" && <div className="card"><ErrorState error={data.error} title="Backup information is unavailable" onRetry={data.reload} /></div>}
      {data.status === "success" && (
        <>
          <Grid cols={2}>
            <ConfigurationCard list={data.data} onCreated={data.reload} />
            <LatestCard list={data.data} />
          </Grid>
          <HistoryCard list={data.data} onChanged={data.reload} onPreview={setPreviewing} />
          {previewing && <RestoreDryRun key={previewing.backupId} backup={previewing} onClose={() => setPreviewing(null)} />}
        </>
      )}
    </Page>
  );
};

const ConfigurationCard: React.FC<{ list: PlatformBackupList; onCreated: () => void }> = ({ list, onCreated }) => {
  const toast = useToast();
  const [confirming, setConfirming] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const withStepUp = useStepUp();
  const onCreate = async () => {
    setBusy(true);
    setError(null);
    try {
      const backup = await withStepUp("platform.backup.create", "platform", createPlatformBackup);
      toast("success", `Backup ${backup.status === "SUCCEEDED" ? "completed" : humanize(backup.status)}.`);
      onCreated();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };
  return (
    <Card title="Configuration" status={list.enabled ? "success" : "warning"}>
      <DataGrid items={[
        { label: "Backups", value: list.enabled ? <Badge tone="success">Enabled</Badge> : <Badge tone="warning">Disabled</Badge> },
        !list.enabled && list.disabledReason ? { label: "Reason", value: list.disabledReason } : null,
        { label: "Scope", value: list.scope.length ? list.scope.map(humanize).join(", ") : "None" },
        { label: "Encryption", value: "AES-256-GCM" },
        { label: "Backup key", value: list.keyCustody === "REMOTE_KMS" ? "Wrapped by the remote KMS" : "Environment key on this host (not production grade)" },
        { label: "Off-site copy", value: humanize(list.offsite) },
        { label: "Immutable storage", value: humanize(list.immutable) },
        { label: "Point-in-time recovery", value: humanize(list.pointInTime) },
        { label: "Retention", value: formatDuration(list.retentionSeconds) },
        { label: "Schedule", value: list.scheduler === "NOT_CONFIGURED" ? "No scheduler configured: manual backups only" : `Every ${formatDuration(list.intervalSeconds)}` },
        { label: "Restore execution", value: "Operator CLI drill into empty restore_drill_* databases, with two-person approval" },
      ]} />
      {error && <Alert tone="danger" live="assertive" title="Backup failed" className="mt-3">{error}</Alert>}
      <div className="mt-3">
        <Button onClick={() => setConfirming(true)} disabled={!list.enabled} icon={<IconDatabaseExport aria-hidden="true" />}>Create backup now</Button>
      </div>
      <ConfirmDialog open={confirming} title="Create a platform backup?" confirmLabel="Create backup" busy={busy} onConfirm={onCreate} onCancel={() => setConfirming(false)}>
        <p className="mb-0">All collections are exported one after another and encrypted. This is not a point-in-time snapshot on a standalone MongoDB, so run it in a quiet period. If a revocation lands during the export, the backup fails and must be run again.</p>
      </ConfirmDialog>
    </Card>
  );
};

const LatestCard: React.FC<{ list: PlatformBackupList }> = ({ list }) => {
  const latest = list.items.find((item) => item.status === "SUCCEEDED") ?? null;
  return (
    <Card title="Last successful backup">
      {!latest ? <EmptyState title="No successful backup yet" /> : (
        <DataGrid items={[
          { label: "Finished", value: formatDateTime(latest.finishedAt) },
          { label: "Duration", value: latest.durationMs !== null ? `${Math.round(latest.durationMs)} ms` : "—" },
          { label: "Size", value: bytes(latest.sizeBytes) },
          { label: "Coverage", value: latest.completeness === "COMPLETE" ? <Badge tone="success">Complete ({latest.components.map(humanize).join(", ")})</Badge> : <Badge tone="warning">Partial: not a restore point</Badge> },
          { label: "Collections", value: latest.collections.length },
          { label: "Documents", value: latest.collections.reduce((sum, item) => sum + item.documents, 0) },
          {
            label: "Integrity",
            value: !latest.lastVerifyResult ? "Not verified yet"
              : latest.lastVerifyResult === "VERIFIED" ? <Badge tone="success">Verified</Badge>
                : <Badge tone="danger">Integrity failed — do not restore</Badge>,
          },
          { label: "Expires", value: formatDateTime(latest.expiresAt) },
        ]} />
      )}
    </Card>
  );
};

const HistoryCard: React.FC<{ list: PlatformBackupList; onChanged: () => void; onPreview: (backup: PlatformBackup) => void }> = ({ list, onChanged, onPreview }) => {
  const toast = useToast();
  const [verifying, setVerifying] = React.useState<string | null>(null);
  const onVerify = async (backup: PlatformBackup) => {
    setVerifying(backup.backupId);
    try {
      await verifyPlatformBackup(backup.backupId);
      toast("success", "Archive decrypted, checksum and contents match the manifest.");
    } catch (cause) {
      toast("danger", describeError(cause));
    } finally {
      setVerifying(null);
      onChanged();
    }
  };
  return (
    <Card title="Backup history" subtitle="Only real job records are listed." flush>
      {list.items.length === 0 ? <EmptyState title="No backups recorded" /> : (
        <Table caption="Platform backup jobs" stackBelow="md">
          <thead>
            <tr><th scope="col">Started</th><th scope="col">Status</th><th scope="col">Duration</th><th scope="col">Size</th><th scope="col">SHA-256</th><th scope="col">Verified</th><th scope="col">Expires</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr>
          </thead>
          <tbody>
            {list.items.map((item) => (
              <tr key={item.backupId}>
                <td data-label="Started">{formatDateTime(item.startedAt)}</td>
                <td data-label="Status"><Badge tone={STATUS_TONE[item.status] ?? "neutral"}>{humanize(item.status)}</Badge>{item.failureCode && <div className="small text-secondary">{humanize(item.failureCode)}</div>}</td>
                <td data-label="Duration">{item.durationMs !== null ? `${Math.round(item.durationMs)} ms` : "—"}</td>
                <td data-label="Size">{bytes(item.sizeBytes)}</td>
                <td data-label="SHA-256">{item.archiveSha256 ? <IdentifierText value={item.archiveSha256} label="archive checksum" copy={false} /> : "—"}</td>
                <td data-label="Verified">
                  {!item.lastVerifiedAt ? "Never" : (
                    <>
                      {item.lastVerifyResult === "VERIFIED" ? <Badge tone="success">Verified</Badge> : <Badge tone="danger">Integrity failed</Badge>}
                      <div className="small text-secondary">{formatDateTime(item.lastVerifiedAt)}</div>
                    </>
                  )}
                </td>
                <td data-label="Expires">{formatDateTime(item.expiresAt)}</td>
                <td data-label="Actions">
                  {item.status === "SUCCEEDED" && (
                    <div className="btn-list flex-nowrap">
                      <Button size="sm" variant="secondary" loading={verifying === item.backupId} onClick={() => onVerify(item)} icon={<IconShieldCheck aria-hidden="true" />}>Verify</Button>
                      <Button size="sm" variant="secondary" onClick={() => onPreview(item)}>Restore dry-run</Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
};

const RestoreDryRun: React.FC<{ backup: PlatformBackup; onClose: () => void }> = ({ backup, onClose }) => {
  const [target, setTarget] = React.useState(() => `restore_drill_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}`);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [preview, setPreview] = React.useState<PlatformRestorePreview | null>(null);
  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setPreview(await previewPlatformRestore(backup.backupId, target.trim()));
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="Restore dry-run" subtitle={<>Backup <IdentifierText value={backup.backupId} label="backup ID" copy={false} /></>} actions={<Button size="sm" variant="ghost" onClick={onClose}>Close</Button>}>
      <form onSubmit={onSubmit} className="row g-3 align-items-end" noValidate>
        <div className="col-md-8">
          <TextField groupClassName="mb-0" label="Drill target database" value={target} onChange={(e) => setTarget(e.target.value)} hint="Must be an empty database named restore_drill_<suffix>, separate from the source." />
        </div>
        <div className="col-md-auto"><Button type="submit" variant="secondary" loading={busy}>Validate plan</Button></div>
      </form>
      {error && <Alert tone="danger" live="assertive" title="Dry-run failed" className="mt-3">{error}</Alert>}
      {preview && (
        <div className="mt-3">
          <DataGrid items={[
            { label: "Source database", value: preview.backup.sourceDatabase },
            { label: "Target database", value: preview.targetDatabase },
            { label: "Target name policy", value: preview.targetNameAccepted ? <Badge tone="success">Accepted</Badge> : <Badge tone="danger">Rejected</Badge> },
            { label: "Archive integrity", value: preview.integrityVerified ? <Badge tone="success">Verified</Badge> : <Badge tone="danger">Not verified</Badge> },
            { label: "Schema version", value: preview.schemaCompatible ? <Badge tone="success">Compatible (v{preview.backup.schemaVersion})</Badge> : <Badge tone="danger">Migration required</Badge> },
            { label: "Documents to restore", value: preview.collections.reduce((sum, item) => sum + item.documents, 0) },
          ]} />
          <div className="mt-3">
            <Table caption="Collections in the archive" inCard={false}>
              <thead><tr><th scope="col">Collection</th><th scope="col">Documents</th><th scope="col">Indexes</th></tr></thead>
              <tbody>
                {preview.collections.map((item) => (
                  <tr key={item.name}><td data-label="Collection">{item.name}</td><td data-label="Documents">{item.documents}</td><td data-label="Indexes">{item.indexes.length}</td></tr>
                ))}
              </tbody>
            </Table>
          </div>
          <Alert tone="warning" title="Execution is not available here" className="mt-3">
            <ul className="mb-0 ps-3">{preview.blockingReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </Alert>
          <div className="mt-3"><DualControlPanel backupId={backup.backupId} targetDatabase={preview.targetDatabase} /></div>
        </div>
      )}
    </Card>
  );
};
