import React from "react";
import { IconDownload, IconFileCheck, IconRestore } from "@tabler/icons-react";
import {
  createWalletBackup,
  listWalletBackups,
  previewWalletRestore,
  restoreWalletBackup,
  type RestoreItem,
  type RestoreJob,
  type RestorePreview,
  type WalletBackup,
} from "../../api/walletBackup.ts";
import type { HolderWallet } from "../../api/wallet.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Checkbox, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { ConfirmDialog } from "../../components/ui/Dialog.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import type { BadgeTone } from "../../components/ui/tones.ts";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";
import {
  ArchiveError,
  MIN_PASSPHRASE_LENGTH,
  archiveFileName,
  decryptBackup,
  encryptBackup,
  isAcceptablePassphrase,
  parseArchive,
  type EncryptedArchive,
} from "../../lib/walletBackupCrypto.ts";
import { useHolderWallet } from "./useHolderWallet.ts";

/** Plain-language meaning of each server-side restore classification. */
const OUTCOME: Record<string, { label: string; tone: BadgeTone }> = {
  RESTORABLE: { label: "Will be restored", tone: "success" },
  RESTORED: { label: "Restored", tone: "success" },
  ALREADY_PRESENT: { label: "Already in wallet", tone: "neutral" },
  HELD_BY_ANOTHER_WALLET: { label: "Held by another wallet", tone: "danger" },
  HOLDER_BINDING_MISMATCH: { label: "Issued to an older DID: ask the issuer to re-issue", tone: "warning" },
  PROOF_INVALID: { label: "Signature or validity failed", tone: "danger" },
  REVOKED: { label: "Revoked by issuer", tone: "danger" },
  STATUS_UNVERIFIABLE: { label: "Status could not be checked", tone: "warning" },
  UNSUPPORTED_ITEM: { label: "Unsupported item", tone: "warning" },
  NOT_ATTEMPTED: { label: "Not attempted", tone: "warning" },
};

const outcomeBadge = (outcome: string) => {
  const meta = OUTCOME[outcome] ?? { label: humanize(outcome), tone: "neutral" as BadgeTone };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
};

const credentialType = (item: RestoreItem) =>
  humanize(item.credentialTypes.find((type) => type !== "VerifiableCredential") ?? "VerifiableCredential");

export const WalletBackupPage: React.FC = () => {
  const wallet = useHolderWallet();
  return (
    <Page
      eyebrow="Holder wallet"
      title="Credential backup"
      description="Keep an encrypted copy of your credentials and restore missing ones."
      breadcrumbs={[{ label: "Wallet", to: "/wallet" }, { label: "Credential backup" }]}
    >
      <Alert tone="info" title="What this backup is, and is not">
        <ul className="mb-0 ps-3">
          <li>Included: the signed credentials in this wallet, exactly as issued.</li>
          <li>Not included: your private key and your guardian setup. Keys cannot be exported; to replace one, use wallet key recovery.</li>
          <li>The file is encrypted in this browser with your passphrase, which is never sent to the platform. Lose the passphrase and the file can never be opened.</li>
          <li>The platform can already read your credentials: it stores them and sends them to this browser. The passphrase protects the file, not your data from the platform.</li>
          <li>Restoring needs your account and the same DID. Credentials issued to an older DID are listed but not restored; the issuer must issue them again.</li>
          <li>Every restored credential is re-checked for signature, holder binding and revocation. A revoked credential stays revoked.</li>
        </ul>
      </Alert>
      {wallet.status === "loading" && <div className="card"><LoadingState label="Opening your wallet" /></div>}
      {wallet.status === "error" && <div className="card"><ErrorState error={wallet.error} title="Your wallet could not be opened" onRetry={wallet.reload} /></div>}
      {wallet.status === "success" && <BackupWorkspace wallet={wallet.data} />}
    </Page>
  );
};

const BackupWorkspace: React.FC<{ wallet: HolderWallet }> = ({ wallet }) => {
  const inventory = useAsync<WalletBackup[]>(() => listWalletBackups(wallet.walletId), [wallet.walletId]);
  return (
    <>
      <Grid cols={2}>
        <CreateBackupCard walletId={wallet.walletId} onCreated={inventory.reload} />
        <RestoreCard wallet={wallet} onRestored={inventory.reload} />
      </Grid>
      <Card title="Backups you created" subtitle="Metadata recorded by the platform. The encrypted files exist only where you saved them." flush>
        {inventory.status === "loading" && <LoadingState label="Loading backups" />}
        {inventory.status === "error" && <ErrorState error={inventory.error} title="Backup records are unavailable" onRetry={inventory.reload} />}
        {inventory.status === "success" && inventory.data.length === 0 && <EmptyState title="No backups yet" description="Create one above and keep the file somewhere safe." />}
        {inventory.status === "success" && inventory.data.length > 0 && (
          <Table caption="Wallet backups" stackBelow="md">
            <thead><tr><th scope="col">Created</th><th scope="col">Credentials</th><th scope="col">Backup ID</th><th scope="col">Integrity digest</th></tr></thead>
            <tbody>
              {inventory.data.map((item) => (
                <tr key={item.backupId}>
                  <td data-label="Created">{formatDateTime(item.createdAt)}</td>
                  <td data-label="Credentials">{item.itemCount}</td>
                  <td data-label="Backup ID"><IdentifierText value={item.backupId} label="backup ID" /></td>
                  <td data-label="Integrity digest"><IdentifierText value={item.contentDigest} label="SHA-256 digest" copy={false} /></td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
};

function download(archive: EncryptedArchive): string {
  const name = archiveFileName(archive);
  const url = URL.createObjectURL(new Blob([JSON.stringify(archive, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return name;
}

const CreateBackupCard: React.FC<{ walletId: string; onCreated: () => void }> = ({ walletId, onCreated }) => {
  const [passphrase, setPassphrase] = React.useState("");
  const [confirmation, setConfirmation] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [created, setCreated] = React.useState<{ backup: WalletBackup; fileName: string } | null>(null);
  const withStepUp = useStepUp();
  const mismatch = confirmation.length > 0 && confirmation !== passphrase;
  const tooShort = passphrase.length > 0 && passphrase.length < MIN_PASSPHRASE_LENGTH;
  const ready = isAcceptablePassphrase(passphrase) && confirmation === passphrase;

  const onCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      const { backup, payload } = await withStepUp("wallet.backup.create", walletId, (token) => createWalletBackup(walletId, token));
      const archive = await encryptBackup(payload, {
        backupId: backup.backupId,
        walletId: backup.walletId,
        createdAt: backup.createdAt,
        itemCount: backup.itemCount,
      }, passphrase);
      setCreated({ backup, fileName: download(archive) });
      onCreated();
    } catch (cause) {
      setError(cause instanceof ArchiveError ? cause.message : describeError(cause));
    } finally {
      // The passphrase lives only in this form and is cleared after every attempt.
      setPassphrase("");
      setConfirmation("");
      setBusy(false);
    }
  };

  return (
    <Card title="Create encrypted backup" subtitle="Encryption happens in this browser (Argon2id, AES-256-GCM).">
      <form onSubmit={onCreate} noValidate>
        <TextField
          label="Backup passphrase"
          type="password"
          autoComplete="new-password"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          hint={`At least ${MIN_PASSPHRASE_LENGTH} varied characters. Store it apart from the file. If you lose it, the file cannot be opened by anyone.`}
          error={tooShort ? `Use at least ${MIN_PASSPHRASE_LENGTH} characters.` : null}
          required
        />
        <TextField
          label="Repeat passphrase"
          type="password"
          autoComplete="new-password"
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          error={mismatch ? "The passphrases do not match." : null}
          required
        />
        {error && <Alert tone="danger" live="assertive" title="Backup not created" className="mb-3">{error}</Alert>}
        {created && (
          <Alert tone="success" live="polite" title="Encrypted backup downloaded" className="mb-3">
            {created.backup.itemCount} credential{created.backup.itemCount === 1 ? "" : "s"} saved as <code>{created.fileName}</code>. Without the passphrase this file cannot be opened.
          </Alert>
        )}
        <Button type="submit" loading={busy} disabled={!ready} icon={<IconDownload aria-hidden="true" />}>Create and download</Button>
      </form>
    </Card>
  );
};

type RestoreStage =
  | { step: "select" }
  | { step: "preview"; preview: RestorePreview; payload: string; idempotencyKey: string }
  | { step: "done"; job: RestoreJob };

const RestoreCard: React.FC<{ wallet: HolderWallet; onRestored: () => void }> = ({ wallet, onRestored }) => {
  const withStepUp = useStepUp();
  const [file, setFile] = React.useState<File | null>(null);
  const [passphrase, setPassphrase] = React.useState("");
  const [stage, setStage] = React.useState<RestoreStage>({ step: "select" });
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [acknowledged, setAcknowledged] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);
  const inputId = React.useId();
  const fileInput = React.useRef<HTMLInputElement>(null);

  const reset = () => {
    setStage({ step: "select" });
    setAcknowledged(false);
    setFile(null);
    setPassphrase("");
    if (fileInput.current) fileInput.current.value = "";
  };

  const onValidate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !passphrase || busy) return;
    setBusy(true);
    setError(null);
    try {
      const archive = parseArchive(await file.text());
      if (archive.walletId !== wallet.walletId) {
        throw new ArchiveError("UNSUPPORTED_FORMAT", "This backup belongs to a different wallet and cannot be restored here.");
      }
      const payload = await decryptBackup(archive, passphrase);
      const preview = await previewWalletRestore(wallet.walletId, archive.backupId, payload);
      setStage({ step: "preview", preview, payload, idempotencyKey: `restore-${crypto.randomUUID()}` });
    } catch (cause) {
      setError(cause instanceof ArchiveError ? cause.message : describeError(cause));
    } finally {
      setPassphrase("");
      setBusy(false);
    }
  };

  const onRestore = async () => {
    if (stage.step !== "preview") return;
    setBusy(true);
    setError(null);
    try {
      const current = stage;
      const job = await withStepUp("wallet.backup.restore", wallet.walletId, (token) =>
        restoreWalletBackup(wallet.walletId, current.preview.backup.backupId, current.payload, current.idempotencyKey, token));
      setStage({ step: "done", job }); // drops the decrypted payload from memory
      onRestored();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setConfirming(false);
      setBusy(false);
    }
  };

  return (
    <Card title="Restore from a backup" subtitle="Only missing, valid and non-revoked credentials are added. Nothing in the wallet is overwritten.">
      {stage.step === "select" && (
        <form onSubmit={onValidate} noValidate>
          <div className="mb-3">
            <label className="form-label required" htmlFor={inputId}>Backup file</label>
            <input
              ref={fileInput}
              id={inputId}
              className="form-control"
              type="file"
              accept="application/json,.json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <small className="form-hint">A file created on this page for this wallet.</small>
          </div>
          <TextField label="Backup passphrase" type="password" autoComplete="off" value={passphrase} onChange={(e) => setPassphrase(e.target.value)} required />
          {error && <Alert tone="danger" live="assertive" title="Backup not accepted" className="mb-3">{error}</Alert>}
          <Button type="submit" variant="secondary" loading={busy} disabled={!file || !passphrase} icon={<IconFileCheck aria-hidden="true" />}>Validate and preview</Button>
        </form>
      )}

      {stage.step === "preview" && (
        <>
          <Alert tone="success" className="mb-3" title="Backup authenticated">
            Decrypted with your passphrase and matched to the integrity record of backup <IdentifierText value={stage.preview.backup.backupId} label="backup ID" copy={false} />.
          </Alert>
          <DataGrid items={[
            { label: "Target wallet", value: <IdentifierText value={wallet.walletId} label="wallet" copy={false} /> },
            { label: "Backup created", value: formatDateTime(stage.preview.backup.createdAt) },
            { label: "Will be restored", value: stage.preview.restorable },
            { label: "Already in wallet", value: stage.preview.alreadyPresent },
            { label: "Not restorable", value: stage.preview.notRestorable },
          ]} />
          <RestoreItemsTable items={stage.preview.items} caption="Restore preview" />
          {error && <Alert tone="danger" live="assertive" title="Restore failed" className="my-3">{error}</Alert>}
          <Checkbox
            className="mt-3"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            label={`Add ${stage.preview.restorable} credential${stage.preview.restorable === 1 ? "" : "s"} to this wallet.`}
          />
          <div className="btn-list mt-3">
            <Button variant="secondary" onClick={reset} disabled={busy}>Cancel</Button>
            <Button onClick={() => setConfirming(true)} disabled={!acknowledged || stage.preview.restorable === 0} icon={<IconRestore aria-hidden="true" />}>Restore</Button>
          </div>
          {stage.preview.restorable === 0 && <p className="text-secondary small mt-2 mb-0">Nothing in this backup needs restoring.</p>}
        </>
      )}

      {stage.step === "done" && (
        <>
          <Alert
            tone={stage.job.status === "COMPLETED" ? "success" : "warning"}
            live="polite"
            className="mb-3"
            title={stage.job.status === "COMPLETED" ? "Restore completed" : stage.job.status === "FAILED" ? "Restore failed" : "Restore partially completed"}
          >
            {stage.job.restored} restored · {stage.job.alreadyPresent} already present · {stage.job.rejected} not restorable
            {stage.job.failureCode ? ` · stopped: ${humanize(stage.job.failureCode)}` : ""}.
          </Alert>
          <RestoreItemsTable items={stage.job.items} caption="Restore result" />
          <div className="btn-list mt-3"><Button variant="secondary" onClick={reset}>Restore another backup</Button></div>
        </>
      )}

      <ConfirmDialog
        open={confirming}
        title="Restore credentials?"
        confirmLabel="Restore"
        busy={busy}
        onConfirm={onRestore}
        onCancel={() => setConfirming(false)}
      >
        <p className="mb-0">
          {stage.step === "preview" ? stage.preview.restorable : 0} credential(s) will be added to your wallet after the platform re-verifies each one. Existing credentials are left unchanged.
        </p>
      </ConfirmDialog>
    </Card>
  );
};

const RestoreItemsTable: React.FC<{ items: RestoreItem[]; caption: string }> = ({ items, caption }) => (
  items.length === 0 ? <EmptyState title="The backup holds no credentials" /> : (
    <div className="mt-3">
      <Table caption={caption} inCard={false}>
        <thead><tr><th scope="col">Credential</th><th scope="col">Result</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.credentialId}>
              <td data-label="Credential">
                <div>{credentialType(item)}</div>
                <IdentifierText value={item.credentialId} label="credential ID" copy={false} />
              </td>
              <td data-label="Result">{outcomeBadge(item.outcome)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
);
