import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Copy, FileCheck2, QrCode, RefreshCw, ShieldCheck } from "lucide-react";
import { QRCodeDisplay } from "../../components/common/QRCodeDisplay";
import { StatusChip } from "../../components/common/StatusChip";
import {
  createOid4vciOffer,
  fetchOid4vciIssuerMetadata,
  getOid4vciOffer,
  type Oid4vciIssuerMetadata,
  type Oid4vciOffer,
} from "../../services/api";

type PageStep = "details" | "review" | "created";
type MetadataState = "loading" | "ready" | "error";

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not supplied" : date.toLocaleString();
};

export const IssueCredentialPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [metadata, setMetadata] = useState<Oid4vciIssuerMetadata | null>(null);
  const [selectedConfiguration, setSelectedConfiguration] = useState("");
  const [subjectJson, setSubjectJson] = useState("");
  const [ttlSeconds, setTtlSeconds] = useState(1800);
  const [userPin, setUserPin] = useState("");
  const [reviewData, setReviewData] = useState<Record<string, unknown> | null>(null);
  const [offer, setOffer] = useState<Oid4vciOffer | null>(null);
  const [offerStatus, setOfferStatus] = useState("");
  const [metadataState, setMetadataState] = useState<MetadataState>("loading");
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [step, setStep] = useState<PageStep>("details");
  const [creating, setCreating] = useState(false);
  const [refreshingOffer, setRefreshingOffer] = useState(false);
  const [pollingError, setPollingError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const configurations = useMemo(
    () => Object.entries(metadata?.credential_configurations_supported || {}),
    [metadata],
  );

  const loadMetadata = useCallback(async () => {
    setMetadataState("loading");
    setMetadataError(null);
    try {
      const result = await fetchOid4vciIssuerMetadata();
      setMetadata(result);
      const requested = searchParams.get("credentialConfigurationId") || "";
      const available = result.credential_configurations_supported;
      setSelectedConfiguration(available[requested] ? requested : Object.keys(available)[0] || "");
      setMetadataState("ready");
    } catch (cause) {
      setMetadata(null);
      setMetadataError(cause instanceof Error ? cause.message : "Issuer metadata could not be loaded.");
      setMetadataState("error");
    }
  }, [searchParams]);

  useEffect(() => { void loadMetadata(); }, [loadMetadata]);

  const refreshOffer = useCallback(async (offerId: string) => {
    try {
      const current = await getOid4vciOffer(offerId);
      setOffer(current);
      setOfferStatus(current.status);
      setPollingError(null);
    } catch (cause) {
      setPollingError(cause instanceof Error ? cause.message : "Offer status could not be refreshed.");
    }
  }, []);

  useEffect(() => {
    const offerId = offer?.offerId;
    if (!offerId || ["CLAIMED", "EXPIRED", "REVOKED"].includes(offerStatus.toUpperCase())) return;
    const interval = window.setInterval(() => { void refreshOffer(offerId); }, 5000);
    return () => window.clearInterval(interval);
  }, [offer?.offerId, offerStatus, refreshOffer]);

  const continueToReview = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!selectedConfiguration || !metadata?.credential_configurations_supported[selectedConfiguration]) {
      setError("Choose a configuration that is currently published in issuer metadata.");
      return;
    }
    let subjectData: unknown;
    try {
      subjectData = JSON.parse(subjectJson);
    } catch {
      setError("Enter valid JSON for the credential subject data.");
      return;
    }
    if (!subjectData || typeof subjectData !== "object" || Array.isArray(subjectData)) {
      setError("Subject data must be a JSON object.");
      return;
    }
    if (userPin && !/^\d{4,8}$/.test(userPin)) {
      setError("The optional user PIN must contain 4 to 8 digits.");
      return;
    }
    setReviewData(subjectData as Record<string, unknown>);
    setStep("review");
  };

  const createOffer = async () => {
    if (!reviewData || !selectedConfiguration) return;
    setError(null);
    setPollingError(null);
    setCreating(true);
    try {
      const created = await createOid4vciOffer({
        credentialConfigurationIds: [selectedConfiguration],
        subjectData: reviewData,
        ttlSeconds,
        userPin: userPin || undefined,
      });
      setOffer(created);
      setOfferStatus(created.status);
      setStep("created");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The credential offer could not be created.");
    } finally {
      setCreating(false);
    }
  };

  const refreshOfferManually = async () => {
    if (!offer?.offerId) return;
    setRefreshingOffer(true);
    await refreshOffer(offer.offerId);
    setRefreshingOffer(false);
  };

  const copyOfferLink = async () => {
    if (!offer?.deepLinkUri) return;
    try {
      await navigator.clipboard.writeText(offer.deepLinkUri);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("The offer link could not be copied. Use the accessible offer URI below.");
    }
  };

  const resetOffer = () => {
    setOffer(null);
    setOfferStatus("");
    setReviewData(null);
    setSubjectJson("");
    setUserPin("");
    setStep("details");
    setError(null);
    setPollingError(null);
  };

  const selectedProfile = metadata?.credential_configurations_supported[selectedConfiguration];
  const selectedName = selectedProfile?.display?.find((item) => item.name)?.name || selectedConfiguration;

  return (
    <main className="workspace-page issuer-page issuer-issue-page">
      <Link className="workspace-text-action issuer-back-link" to="/issuer"><ArrowLeft size={16} aria-hidden="true" /> Issuer overview</Link>
      <header className="workspace-page-header issuer-page-header">
        <div>
          <p className="workspace-eyebrow">OID4VCI · Offer creation</p>
          <h1>Create a credential offer</h1>
          <p>Use a published configuration, review the offer details, then create a claim link for a holder wallet.</p>
        </div>
      </header>

      {metadataState === "loading" && (
        <section className="issuer-data-state" role="status" aria-busy="true">
          <span className="issuer-loading-mark" aria-hidden="true"><RefreshCw size={17} /></span>
          <div><strong>Loading issuer configurations</strong><p>Offer creation will be available when published metadata is loaded.</p></div>
        </section>
      )}
      {metadataState === "error" && (
        <section className="issuer-data-state issuer-data-state--error" role="alert">
          <span className="issuer-loading-mark" aria-hidden="true"><FileCheck2 size={18} /></span>
          <div className="issuer-data-state__copy"><strong>Issuer metadata could not be loaded</strong><p>{metadataError}</p></div>
          <button type="button" className="workspace-secondary-action" onClick={() => void loadMetadata()}>Retry</button>
        </section>
      )}
      {metadataState === "ready" && configurations.length === 0 && (
        <section className="issuer-data-state issuer-data-state--empty">
          <span className="issuer-loading-mark" aria-hidden="true"><FileCheck2 size={18} /></span>
          <div><strong>Offer creation is unavailable</strong><p>The metadata endpoint returned no credential configurations supported for issuance.</p></div>
        </section>
      )}

      {error && <div className="workspace-error issuer-form-error" role="alert">{error}</div>}

      {metadataState === "ready" && configurations.length > 0 && step !== "created" && (
        <>
          <ol className="issuer-stepper" aria-label="Offer creation steps">
            <li className={step === "details" ? "is-current" : "is-complete"}><span>{step === "details" ? "1" : <Check size={14} aria-hidden="true" />}</span><div><strong>Offer details</strong><small>Configuration and subject data</small></div></li>
            <li className={step === "review" ? "is-current" : ""}><span>2</span><div><strong>Review</strong><small>Confirm before creating</small></div></li>
          </ol>

          {step === "details" && (
            <form className="workspace-panel workspace-form issuer-form-panel" onSubmit={continueToReview}>
              <div className="issuer-form-section-heading"><span className="issuer-config-card__icon"><FileCheck2 size={19} aria-hidden="true" /></span><div><h2>Offer details</h2><p>Configuration choices come from the current issuer metadata response.</p></div></div>
              <div className="workspace-form-grid issuer-form-grid">
                <label className="workspace-field">
                  <span>Credential configuration</span>
                  <select className="form-select" value={selectedConfiguration} onChange={(event) => setSelectedConfiguration(event.target.value)} required>
                    {configurations.map(([id, configuration]) => <option key={id} value={id}>{configuration.display?.find((item) => item.name)?.name || id}</option>)}
                  </select>
                  <small className="issuer-field-detail"><code>{selectedConfiguration}</code>{selectedProfile?.format && <> · {selectedProfile.format}</>}</small>
                </label>
                <label className="workspace-field">
                  <span>Offer validity</span>
                  <select className="form-select" value={ttlSeconds} onChange={(event) => setTtlSeconds(Number(event.target.value))}>
                    <option value={300}>5 minutes</option><option value={900}>15 minutes</option><option value={1800}>30 minutes</option><option value={3600}>1 hour</option>
                  </select>
                  <small className="issuer-field-detail">The service will return the authoritative expiry time.</small>
                </label>
              </div>
              <label className="workspace-field issuer-subject-field">
                <span>Credential subject data <small>JSON object</small></span>
                <textarea className="form-textarea workspace-json-input" value={subjectJson} onChange={(event) => setSubjectJson(event.target.value)} placeholder="Paste the JSON object for this credential subject" spellCheck={false} required aria-describedby="issuer-subject-help" />
                <small id="issuer-subject-help">Enter only attributes verified by your organization and authorized for issuance. Data is sent to the Identity Service when you confirm creation.</small>
              </label>
              <label className="workspace-field issuer-pin-field">
                <span>User PIN <small>Optional</small></span>
                <input className="form-input" type="password" inputMode="numeric" autoComplete="new-password" maxLength={8} value={userPin} onChange={(event) => setUserPin(event.target.value)} placeholder="4–8 digits" aria-describedby="issuer-pin-help" />
                <small id="issuer-pin-help">If used, the holder needs this PIN when claiming the offer.</small>
              </label>
              <div className="issuer-form-footer">
                <p><ShieldCheck size={16} aria-hidden="true" /> Creating an offer does not issue a credential. The holder must complete the claim flow.</p>
                <button type="submit" className="workspace-primary-action">Review offer <ArrowRight size={16} aria-hidden="true" /></button>
              </div>
            </form>
          )}

          {step === "review" && reviewData && (
            <section className="workspace-panel issuer-review-panel" aria-labelledby="issuer-review-title">
              <div className="issuer-form-section-heading"><span className="issuer-config-card__icon"><ShieldCheck size={19} aria-hidden="true" /></span><div><h2 id="issuer-review-title">Review offer details</h2><p>Confirm the configuration and offer settings before sending the request to the Identity Service.</p></div></div>
              <dl className="issuer-review-list">
                <div><dt>Credential configuration</dt><dd><strong>{selectedName}</strong><code>{selectedConfiguration}</code></dd></div>
                <div><dt>Offer validity</dt><dd>{ttlSeconds / 60} minutes</dd></div>
                <div><dt>Recipient identity</dt><dd>No recipient identifier is included in the current offer request.</dd></div>
                <div><dt>User PIN</dt><dd>{userPin ? "Configured (value hidden)" : "Not configured"}</dd></div>
                <div><dt>Subject attributes</dt><dd>{Object.keys(reviewData).length ? Object.keys(reviewData).join(", ") : "No attribute keys supplied"}</dd></div>
              </dl>
              <p className="issuer-review-note">The attribute values are intentionally not repeated in this review screen. Confirm only if the submitted data is accurate and authorized.</p>
              <div className="issuer-review-actions">
                <button type="button" className="workspace-secondary-action" onClick={() => { setError(null); setStep("details"); }}>Back to edit</button>
                <button type="button" className="workspace-primary-action" onClick={() => void createOffer()} disabled={creating}>
                  {creating ? <><RefreshCw size={16} className="spin" aria-hidden="true" /> Creating offer…</> : <><QrCode size={16} aria-hidden="true" /> Create offer</>}
                </button>
              </div>
            </section>
          )}
        </>
      )}

      {step === "created" && offer && (
        <section className="workspace-panel issuer-created-panel" aria-labelledby="issuer-created-title">
          <div className="issuer-created-heading">
            <span className="issuer-created-heading__icon"><CheckCircle2 size={22} aria-hidden="true" /></span>
            <div><p className="workspace-eyebrow">Offer returned by service</p><h2 id="issuer-created-title">Credential offer created</h2><p>A credential is not issued until the holder completes the claim flow.</p></div>
            <StatusChip status={offerStatus || offer.status} />
          </div>
          <div className="issuer-created-content">
            <div className="issuer-created-qr">
              {offer.deepLinkUri ? <QRCodeDisplay value={offer.deepLinkUri} size={196} title="Holder claim offer" subtitle="Scan with a compatible wallet" /> : <div className="issuer-data-state issuer-data-state--error" role="alert"><strong>QR unavailable</strong><p>The service response did not include an offer link.</p></div>}
            </div>
            <dl className="issuer-review-list issuer-offer-result-details">
              <div><dt>Offer ID</dt><dd><code>{offer.offerId}</code></dd></div>
              <div><dt>Configuration</dt><dd>{offer.credentialConfigurationIds.join(", ") || "Not supplied"}</dd></div>
              <div><dt>Current status</dt><dd><StatusChip status={offerStatus || offer.status} size="sm" /></dd></div>
              <div><dt>Expires</dt><dd>{formatDate(offer.expiresAt)}</dd></div>
              <div><dt>Issuer endpoint</dt><dd><code>{offer.credentialIssuer || "Not supplied"}</code></dd></div>
            </dl>
          </div>
          {pollingError && <div className="workspace-inline-error issuer-poll-error" role="status">Status refresh failed: {pollingError}</div>}
          <div className="issuer-created-actions">
            {offer.deepLinkUri && <button type="button" className="workspace-secondary-action" onClick={() => void copyOfferLink()}><Copy size={16} aria-hidden="true" /> {copied ? "Link copied" : "Copy offer link"}</button>}
            <button type="button" className="workspace-secondary-action" onClick={() => void refreshOfferManually()} disabled={refreshingOffer}>
              <RefreshCw size={16} aria-hidden="true" className={refreshingOffer ? "spin" : undefined} /> Refresh status
            </button>
            <button type="button" className="workspace-primary-action" onClick={resetOffer}>Create another offer</button>
          </div>
          {offer.deepLinkUri && <details className="issuer-uri-details"><summary>Show offer link</summary><code>{offer.deepLinkUri}</code></details>}
          {error && <div className="workspace-error" role="alert">{error}</div>}
        </section>
      )}
    </main>
  );
};
