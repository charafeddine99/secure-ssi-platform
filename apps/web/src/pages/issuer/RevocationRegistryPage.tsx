import React, { useRef, useState } from "react";
import { AlertCircle, CheckCircle2, RefreshCw, Search, ShieldOff } from "lucide-react";
import { fetchCredentialStatus, revokeCredential, type CredentialStatusSnapshot } from "../../services/api";
import { StatusChip } from "../../components/common/StatusChip";

const formatRecordedAt = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not supplied" : date.toLocaleString();
};

export const RevocationRegistryPage: React.FC = () => {
  const [credentialId, setCredentialId] = useState("");
  const [reason, setReason] = useState("AFFILIATION_TERMINATED");
  const [status, setStatus] = useState<CredentialStatusSnapshot | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [hasLookedUp, setHasLookedUp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const confirmationRef = useRef<HTMLDialogElement | null>(null);

  const lookupStatus = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    const id = credentialId.trim();
    if (!id) return;
    setLookupLoading(true);
    setError(null);
    setNotice(null);
    setStatus(null);
    setHasLookedUp(false);
    try {
      const snapshot = await fetchCredentialStatus(id);
      setStatus(snapshot);
      setHasLookedUp(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Credential status could not be loaded.");
    } finally {
      setLookupLoading(false);
    }
  };

  const openConfirmation = () => {
    setDialogError(null);
    confirmationRef.current?.showModal();
  };

  const handleRevoke = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!status || status.status !== "ACTIVE" || !reason.trim()) return;
    setRevoking(true);
    setDialogError(null);
    setError(null);
    setNotice(null);
    try {
      await revokeCredential(status.credential_id, reason);
      confirmationRef.current?.close();
      try {
        const updated = await fetchCredentialStatus(status.credential_id);
        setStatus(updated);
        setNotice(updated.status === "REVOKED"
          ? "The Identity Service confirms that this credential is revoked."
          : `The revoke request returned, but the latest service status is ${updated.status}.`);
      } catch (refreshCause) {
        setStatus(null);
        setHasLookedUp(false);
        const message = refreshCause instanceof Error ? refreshCause.message : "the status could not be reloaded";
        setNotice(`The service accepted the revocation request, but the status refresh failed: ${message}`);
      }
    } catch (cause) {
      setDialogError(cause instanceof Error ? cause.message : "Credential revocation failed.");
    } finally {
      setRevoking(false);
    }
  };

  const statusDescription: Record<string, string> = {
    ACTIVE: "The service reports this credential as active. Revocation can be requested by an authorized issuer.",
    SUSPENDED: "The service reports this credential as suspended. This screen does not resume or revoke suspended credentials.",
    REVOKED: "The service reports this credential as revoked. Revocation cannot be repeated from this screen.",
    EXPIRED: "The service reports this credential as expired. No revocation action is available.",
    UNKNOWN: "The service could not establish a known lifecycle state for this credential. No action is available.",
  };

  return (
    <main className="workspace-page issuer-page issuer-status-page">
      <header className="workspace-page-header issuer-page-header">
        <div>
          <p className="workspace-eyebrow">Issuer · Credential lifecycle</p>
          <h1>Credential status</h1>
          <p>Look up a credential by its exact identifier. The service returns the current status and enforces issuer authorization for revocation.</p>
        </div>
      </header>

      <section className="workspace-panel issuer-lookup-panel" aria-labelledby="issuer-lookup-title">
        <div className="issuer-form-section-heading"><span className="issuer-config-card__icon"><Search size={19} aria-hidden="true" /></span><div><h2 id="issuer-lookup-title">Find a credential</h2><p>Use an identifier from an authorized issuance record.</p></div></div>
        <form className="issuer-lookup-form" onSubmit={(event) => void lookupStatus(event)}>
        <label className="workspace-field" htmlFor="issuer-credential-id">
            <span>Credential ID</span>
            <input id="issuer-credential-id" className="form-input issuer-credential-id-input" value={credentialId} onChange={(event) => { setCredentialId(event.target.value); setStatus(null); setHasLookedUp(false); setNotice(null); setError(null); }} placeholder="Paste the exact credential identifier" autoComplete="off" required disabled={lookupLoading} />
          </label>
          <button type="submit" className="workspace-primary-action" disabled={lookupLoading || !credentialId.trim()}>
            {lookupLoading ? <><RefreshCw size={16} className="spin" aria-hidden="true" /> Checking…</> : <><Search size={16} aria-hidden="true" /> Check status</>}
          </button>
        </form>
        <p className="issuer-lookup-footnote"><ShieldOff size={15} aria-hidden="true" /> No global credential inventory is exposed. A status lookup does not grant permission to revoke.</p>
      </section>

      {lookupLoading && <div className="issuer-data-state" role="status" aria-busy="true"><span className="issuer-loading-mark" aria-hidden="true"><RefreshCw size={17} /></span><div><strong>Checking current status</strong><p>Waiting for the credential status service.</p></div></div>}
      {error && <div className="workspace-error issuer-status-error" role="alert"><AlertCircle size={17} aria-hidden="true" /> <span>{error}</span></div>}
      {notice && <div className="workspace-notice issuer-status-notice" role="status"><CheckCircle2 size={17} aria-hidden="true" /> <span>{notice}</span></div>}

      {hasLookedUp && status && (
        <section className="workspace-panel issuer-status-result" aria-labelledby="issuer-status-result-title">
          <div className="issuer-status-result__heading">
            <div><p className="workspace-eyebrow">Authoritative response</p><h2 id="issuer-status-result-title">Credential status</h2></div>
            <StatusChip status={status.status} />
          </div>
          <dl className="issuer-review-list issuer-status-facts">
            <div><dt>Credential ID</dt><dd><code>{status.credential_id}</code></dd></div>
            <div><dt>Current state</dt><dd>{status.status}</dd></div>
            {status.revocation_reason && <div><dt>Recorded reason</dt><dd>{status.revocation_reason}</dd></div>}
            {status.revoked_at && <div><dt>Revoked at</dt><dd>{formatRecordedAt(status.revoked_at)}</dd></div>}
          </dl>
          <p className="issuer-status-explanation">{statusDescription[status.status] || `The service returned status “${status.status}”. No revocation action is available for this state.`}</p>
          {status.status === "ACTIVE" && (
            <div className="issuer-revoke-action-row">
              <p>Revocation is permanent. Confirm the exact credential and reason before submitting.</p>
              <button type="button" className="workspace-danger-action" onClick={openConfirmation}><ShieldOff size={16} aria-hidden="true" /> Review revocation</button>
            </div>
          )}
        </section>
      )}

      {!hasLookedUp && !lookupLoading && !error && (
        <section className="issuer-status-empty" aria-label="No credential selected">
          <span className="issuer-loading-mark" aria-hidden="true"><ShieldOff size={18} /></span>
          <div><strong>Credential status appears here</strong><p>Enter an identifier above to load its current service-reported state.</p></div>
        </section>
      )}

      <dialog className="issuer-confirm-dialog" ref={confirmationRef} aria-labelledby="issuer-confirm-title" aria-describedby="issuer-confirm-description" onCancel={() => setDialogError(null)}>
        <form onSubmit={(event) => void handleRevoke(event)}>
          <div className="issuer-confirm-dialog__icon"><ShieldOff size={20} aria-hidden="true" /></div>
          <p className="workspace-eyebrow">Permanent action</p>
          <h2 id="issuer-confirm-title">Confirm credential revocation</h2>
          <p id="issuer-confirm-description">The request will be authorized and recorded by the Identity Service. You cannot undo a successful revocation.</p>
          {status && <div className="issuer-confirm-credential"><span>Credential ID</span><code>{status.credential_id}</code></div>}
          <label className="workspace-field">
            <span>Revocation reason</span>
            <select className="form-select" value={reason} onChange={(event) => setReason(event.target.value)} disabled={revoking}>
              <option value="AFFILIATION_TERMINATED">Affiliation ended</option>
              <option value="SUPERSEDED">Credential replaced</option>
              <option value="SECURITY_CONCERN">Security concern</option>
              <option value="UNSPECIFIED">Other / unspecified</option>
            </select>
          </label>
          {dialogError && <div className="workspace-error issuer-dialog-error" role="alert">{dialogError}</div>}
          <div className="issuer-confirm-dialog__actions">
            <button type="button" className="workspace-secondary-action" onClick={() => confirmationRef.current?.close()} disabled={revoking}>Cancel</button>
            <button type="submit" className="workspace-danger-action" disabled={revoking || !status}>
              {revoking ? <><RefreshCw size={16} className="spin" aria-hidden="true" /> Revoking…</> : <><ShieldOff size={16} aria-hidden="true" /> Revoke credential</>}
            </button>
          </div>
        </form>
      </dialog>
    </main>
  );
};
