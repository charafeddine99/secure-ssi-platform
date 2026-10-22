import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowLeft, ArrowRight, Check, CheckCircle2, Clock3, FileCheck2, Info, LoaderCircle, QrCode, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import { QRCodeDisplay } from "../../components/common/QRCodeDisplay";
import { NinePointVerificationMatrix } from "../../components/verification/NinePointVerificationMatrix";
import { createOid4vpSession, getOid4vpSession, Oid4vpSession } from "../../services/api";

const credentialType = "UniversityAffiliationCredential";
const supportedFields = [
  { id: "affiliation", label: "Affiliation", detail: "Student, faculty or staff" },
  { id: "programCode", label: "Program code", detail: "Education programme identifier" },
  { id: "degree", label: "Degree", detail: "Credentialed qualification" },
  { id: "graduationYear", label: "Graduation year", detail: "Year recorded in the credential" },
] as const;

const formatExpiry = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Provided by the service" : date.toLocaleString();
};

export const CreateRequestPage: React.FC = () => {
  const [purpose, setPurpose] = useState("");
  const [claims, setClaims] = useState<string[]>([]);
  const [ttlSeconds, setTtlSeconds] = useState(600);
  const [showSummary, setShowSummary] = useState(false);
  const [creating, setCreating] = useState(false);
  const [session, setSession] = useState<Oid4vpSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    const sessionId = session?.sessionId;
    const expiresAt = session?.expiresAt;
    if (!sessionId || session?.status !== "PENDING") return;
    let active = true;
    const poll = async () => {
      const expiry = Date.parse(expiresAt || "");
      if (Number.isFinite(expiry) && Date.now() >= expiry) {
        if (active) setSession((current) => current?.sessionId === sessionId ? { ...current, status: "EXPIRED" } : current);
        return;
      }
      try {
        const updated = await getOid4vpSession(sessionId);
        if (!active) return;
        setSession(updated);
        setPollError(null);
      } catch (cause) {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : "Session status could not be refreshed.";
        if (message.includes("410")) {
          setSession((current) => current?.sessionId === sessionId ? { ...current, status: "EXPIRED" } : current);
        } else setPollError("The service could not refresh this request. It will retry automatically.");
      }
    };
    void poll();
    const interval = window.setInterval(() => void poll(), 2000);
    return () => { active = false; window.clearInterval(interval); };
  }, [session?.sessionId, session?.status, session?.expiresAt]);

  const toggleField = (field: string) => setClaims((current) => current.includes(field)
    ? current.filter((item) => item !== field)
    : [...current, field]);

  const createSession = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!claims.length) {
      setError("Select at least one credential field to match.");
      return;
    }
    setCreating(true);
    try {
      const created = await createOid4vpSession({
        purpose: purpose.trim(),
        requestedCredentialTypes: [credentialType],
        requestedFields: claims,
        ttlSeconds,
      });
      setSession(created);
      setPollError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The verification service could not create this request.");
    } finally {
      setCreating(false);
    }
  };

  const reset = () => { setSession(null); setError(null); setPollError(null); };
  const pending = session?.status === "PENDING";
  const verified = session?.status === "VERIFIED";
  const rejected = session?.status === "REJECTED";
  const expired = session?.status === "EXPIRED";

  return (
    <main className="workspace-page verifier-request-page">
      <Link className="workspace-text-action verifier-back-link" to="/verifier"><ArrowLeft size={16} aria-hidden="true" /> Verifier workspace</Link>
      <header className="workspace-page-header">
        <div><p className="workspace-eyebrow">OpenID for Verifiable Presentations</p><h1>Create a presentation request</h1><p>Set the purpose and credential fields the service should match, then share the generated request with the holder.</p></div>
        <span className="verifier-protocol-label">OID4VP 1.0 <span aria-hidden="true">·</span> DCQL</span>
      </header>
      {error && <div className="workspace-error" role="alert"><AlertCircle size={18} aria-hidden="true" />{error}</div>}

      {!session ? (
        <form className="workspace-panel workspace-form verifier-request-form" onSubmit={(event) => void createSession(event)}>
          <section className="verifier-form-section" aria-labelledby="request-context-title">
            <div className="verifier-form-section__heading"><span className="workspace-icon-tile"><FileCheck2 size={19} aria-hidden="true" /></span><div><h2 id="request-context-title">Request context</h2><p>Tell the holder why the credential is needed.</p></div></div>
            <label className="workspace-field" htmlFor="verification-purpose">
              <span>Purpose</span>
              <input id="verification-purpose" value={purpose} onChange={(event) => setPurpose(event.target.value)} placeholder="For example, confirm current university affiliation" maxLength={240} required aria-describedby="purpose-help" />
              <small id="purpose-help">This text is sent to the Identity Service and included in the holder request.</small>
            </label>
          </section>

          <section className="verifier-form-section" aria-labelledby="credential-profile-title">
            <div className="verifier-form-section__heading"><span className="workspace-icon-tile"><ShieldCheck size={19} aria-hidden="true" /></span><div><h2 id="credential-profile-title">Credential profile</h2><p>Only the profile currently supported by this verifier flow is available.</p></div></div>
            <div className="verifier-credential-profile"><span className="verifier-credential-profile__icon"><FileCheck2 size={20} aria-hidden="true" /></span><span><strong>Higher education affiliation</strong><code>{credentialType}</code></span><span className="verifier-supported-label"><Check size={14} aria-hidden="true" /> Supported</span></div>
          </section>

          <section className="verifier-form-section" aria-labelledby="requested-fields-title">
            <div className="verifier-form-section__heading"><span className="workspace-icon-tile"><Info size={19} aria-hidden="true" /></span><div><h2 id="requested-fields-title">Credential fields to match</h2><p>Select only the fields relevant to this verification.</p></div><span className="verifier-selected-count">{claims.length} selected</span></div>
            <div className="verifier-field-options">
              {supportedFields.map((field) => {
                const checked = claims.includes(field.id);
                return <label className={"verifier-field-option" + (checked ? " is-selected" : "")} key={field.id}>
                  <input type="checkbox" checked={checked} onChange={() => toggleField(field.id)} />
                  <span className="verifier-field-option__check" aria-hidden="true">{checked ? <Check size={14} /> : null}</span>
                  <span className="verifier-field-option__copy"><strong>{field.label}</strong><small>{field.detail}</small></span>
                </label>;
              })}
            </div>
            <div className="workspace-notice verifier-disclosure-notice"><Info size={17} aria-hidden="true" /><p><strong>Credential matching is not selective disclosure.</strong> These fields define the DCQL match. The current Data Integrity flow may transmit the complete signed credential; it does not cryptographically disclose only the selected fields.</p></div>
          </section>

          <section className="verifier-form-section verifier-duration-section" aria-labelledby="request-duration-title">
            <div className="verifier-form-section__heading"><span className="workspace-icon-tile"><Clock3 size={19} aria-hidden="true" /></span><div><h2 id="request-duration-title">Request lifetime</h2><p>The request expires after the selected interval.</p></div></div>
            <label className="workspace-field" htmlFor="request-lifetime"><span>Session duration</span><select id="request-lifetime" value={ttlSeconds} onChange={(event) => setTtlSeconds(Number(event.target.value))}><option value={300}>5 minutes</option><option value={600}>10 minutes</option><option value={1800}>30 minutes</option></select></label>
          </section>

          <div className="verifier-request-footer">
            <div className="verifier-request-footer__actions">
              <button className="workspace-secondary-action" type="button" onClick={() => setShowSummary((current) => !current)} aria-expanded={showSummary}>{showSummary ? "Hide request summary" : "Review request summary"}</button>
              <button className="workspace-primary-action" type="submit" disabled={creating || !purpose.trim() || claims.length === 0}>{creating ? <LoaderCircle className="verifier-spin" size={17} aria-hidden="true" /> : <QrCode size={17} aria-hidden="true" />}{creating ? "Creating request…" : "Create request"}{!creating && <ArrowRight size={16} aria-hidden="true" />}</button>
            </div>
            {showSummary && <div className="verifier-request-summary" role="region" aria-label="Request summary"><strong>Holder request summary</strong><dl><div><dt>Purpose</dt><dd>{purpose.trim() || "Enter a purpose to continue"}</dd></div><div><dt>Credential</dt><dd>{credentialType}</dd></div><div><dt>Matching fields</dt><dd>{claims.length ? claims.map((id) => supportedFields.find((field) => field.id === id)?.label || id).join(", ") : "None selected"}</dd></div><div><dt>Request expires</dt><dd>{Math.round(ttlSeconds / 60)} minutes after creation</dd></div></dl><p>The wallet displays its own consent screen. This summary does not predict its exact layout or change what the credential contains.</p></div>}
          </div>
        </form>
      ) : (
        <section className="workspace-panel verifier-session-panel" aria-labelledby="session-title">
          <header className="verifier-session-header">
            <div className={"verifier-session-mark" + (verified ? " is-success" : rejected || expired ? " is-error" : "")}>{pending ? <QrCode size={23} aria-hidden="true" /> : verified ? <CheckCircle2 size={23} aria-hidden="true" /> : <XCircle size={23} aria-hidden="true" />}</div>
            <div className="verifier-session-title"><p className="workspace-eyebrow">Presentation request</p><h2 id="session-title">{pending ? "Waiting for a holder" : verified ? "Presentation verified" : expired ? "Request expired" : "Presentation not accepted"}</h2><p>{pending ? "Scan with a compatible wallet. The service checks for a submitted presentation automatically." : verified ? "The Identity Service returned a verified outcome for this session." : expired ? "This session has expired. Create a new request to continue." : session.consentStatus === "REJECTED" ? "The holder declined to share the requested credential." : "The Identity Service did not accept the submitted presentation."}</p></div>
            <span className={"verifier-session-status is-" + session.status.toLowerCase()} role="status">{session.status}</span>
          </header>
          {pending && <div className="verifier-session-body"><div className="verifier-session-qr"><QRCodeDisplay value={session.deepLinkUri || session.qrPayload} size={220} title="Scan with a compatible wallet" subtitle="OpenID4VP · DCQL" /></div><div className="verifier-session-details"><div className="verifier-session-instruction"><span className="verifier-pulse" aria-hidden="true" /><span>Waiting for a holder response</span><small aria-live="polite">Request status refreshes automatically.</small></div><dl><div><dt>Purpose</dt><dd>{session.purpose}</dd></div><div><dt>Credential</dt><dd>{session.requestedCredentialTypes.join(", ")}</dd></div><div><dt>Requested matching fields</dt><dd>{session.requestedFields.join(", ") || "No fields returned"}</dd></div><div><dt>Expires</dt><dd>{formatExpiry(session.expiresAt)}</dd></div><div><dt>Session reference</dt><dd><code>{session.sessionId}</code></dd></div></dl>{pollError && <p className="workspace-error verifier-poll-error" role="status"><RefreshCw size={16} aria-hidden="true" />{pollError}</p>}</div></div>}
          {rejected && <div className="verifier-session-outcome is-rejected" role="status"><XCircle size={18} aria-hidden="true" /><div><strong>{session.consentStatus === "REJECTED" ? "Consent declined" : "Verification rejected"}</strong><p>{session.rejectionReason || (session.consentStatus === "REJECTED" ? "The holder chose not to share this credential." : "No further rejection detail was returned by the service.")}</p></div></div>}
          {expired && <div className="verifier-session-outcome is-expired" role="status"><Clock3 size={18} aria-hidden="true" /><div><strong>Session is no longer active</strong><p>The session lifetime ended or the service returned an expired status.</p></div></div>}
          {verified && session.verificationResult && <NinePointVerificationMatrix result={session.verificationResult} disclosedClaims={session.disclosedClaims} aiRiskScore={session.aiRiskScore} sessionId={session.sessionId} />}
          {verified && !session.verificationResult && <div className="workspace-notice verifier-result-notice" role="status"><Info size={17} aria-hidden="true" /><p>The service marked this session verified but did not return detailed policy evidence.</p></div>}
          <footer className="verifier-session-footer"><button className="workspace-primary-action" type="button" onClick={reset}><QrCode size={16} aria-hidden="true" /> Create another request</button><Link className="workspace-secondary-action" to="/verifier">Return to workspace</Link></footer>
        </section>
      )}
    </main>
  );
};
