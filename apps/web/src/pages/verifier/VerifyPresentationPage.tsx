import React, { useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowLeft, CheckCircle2, CircleHelp, Clock3, Search, ShieldAlert } from "lucide-react";
import { StatusChip } from "../../components/common/StatusChip";
import { PresentationVerificationResult, verifyPresentation } from "../../services/api";

export const VerifyPresentationPage: React.FC = () => {
  const [presentationJson, setPresentationJson] = useState("");
  const [expectedChallenge, setExpectedChallenge] = useState("");
  const [expectedDomain, setExpectedDomain] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<PresentationVerificationResult | null>(null);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);

  const handleVerify = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setResult(null);
    setElapsedMs(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(presentationJson);
    } catch {
      setFormError("Presentation data must be valid JSON.");
      return;
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) || !("presentation" in parsed)) {
      setFormError("Provide a JSON object containing a presentation property.");
      return;
    }
    if (!expectedChallenge.trim() || !expectedDomain.trim()) {
      setFormError("Enter the challenge and domain issued for this verification request.");
      return;
    }
    setVerifying(true);
    const startedAt = performance.now();
    try {
      const verification = await verifyPresentation({
        ...(parsed as Record<string, unknown>),
        expectedChallenge: expectedChallenge.trim(),
        expectedDomain: expectedDomain.trim(),
      });
      setElapsedMs(performance.now() - startedAt);
      setResult(verification);
    } catch (cause) {
      setElapsedMs(performance.now() - startedAt);
      setFormError(cause instanceof Error ? cause.message : "Verification service request failed.");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <main className="workspace-page verifier-verify-page">
      <Link className="workspace-text-action verifier-back-link" to="/verifier"><ArrowLeft size={16} aria-hidden="true" /> Verifier workspace</Link>
      <header className="workspace-page-header">
        <div><p className="workspace-eyebrow">Presentation verification</p><h1>Verify a presentation</h1><p>Submit the presentation received for a request together with that request’s challenge and domain.</p></div>
        <span className="verifier-protocol-label"><Search size={15} aria-hidden="true" /> Identity Service</span>
      </header>
      {formError && <div className="workspace-error" role="alert"><AlertCircle size={18} aria-hidden="true" /><span>{formError}</span></div>}
      <form className="workspace-panel workspace-form verifier-verify-form" onSubmit={(event) => void handleVerify(event)} aria-busy={verifying}>
        <div className="verifier-form-section__heading">
          <span className="workspace-icon-tile"><Search size={19} aria-hidden="true" /></span>
          <div><h2>Presentation payload</h2><p>Use the payload returned by the holder flow. The service decides the verification outcome.</p></div>
        </div>
        <label className="workspace-field" htmlFor="presentation-json">
          <span>Verifiable Presentation JSON</span>
          <textarea id="presentation-json" className="form-textarea workspace-json-input verifier-json-input" value={presentationJson} onChange={(event) => setPresentationJson(event.target.value)} placeholder="Paste JSON containing the presentation property" spellCheck={false} autoCapitalize="off" autoCorrect="off" required aria-describedby="presentation-help" />
          <small id="presentation-help">Values remain in this form until you leave or replace them.</small>
        </label>
        <div className="workspace-form-grid">
          <label className="workspace-field" htmlFor="expected-challenge">
            <span>Expected challenge</span>
            <input id="expected-challenge" value={expectedChallenge} onChange={(event) => setExpectedChallenge(event.target.value)} autoComplete="off" required />
            <small>Enter the challenge issued for this presentation request.</small>
          </label>
          <label className="workspace-field" htmlFor="expected-domain">
            <span>Expected domain</span>
            <input id="expected-domain" value={expectedDomain} onChange={(event) => setExpectedDomain(event.target.value)} autoComplete="url" required />
            <small>Enter the domain bound to the request.</small>
          </label>
        </div>
        <div className="workspace-notice verifier-verification-notice"><ShieldAlert size={17} aria-hidden="true" /><p>Submit only to the verification service authorized for this presentation. This screen reports the service response; it does not create a separate history record or infer checks the API did not return.</p></div>
        <div className="workspace-form-actions verifier-verify-actions">
          <span className="workspace-footnote">A rejected or unavailable result is never treated as verified.</span>
          <button type="submit" className="workspace-primary-action" disabled={verifying}>{verifying ? <Clock3 size={16} aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}{verifying ? "Submitting to service…" : "Verify presentation"}</button>
        </div>
      </form>
      <section className="workspace-panel workspace-verification-result verifier-result-panel" aria-labelledby="verification-result-title" aria-live="polite">
        <div className="workspace-section-heading"><div><p className="workspace-eyebrow">Service response</p><h2 id="verification-result-title">Verification result</h2></div>{result && <StatusChip status={result.status} />}</div>
        {!result && <div className="verifier-result-waiting" role={verifying ? "status" : "note"}>{verifying ? <Clock3 size={20} aria-hidden="true" /> : <CircleHelp size={20} aria-hidden="true" />}<span>{verifying ? "Waiting for the Identity Service response…" : "No presentation has been checked in this session."}</span></div>}
        {result && <div className={"verifier-result-outcome " + (result.verified ? "is-verified" : "is-rejected")} role="status">{result.verified ? <CheckCircle2 size={22} aria-hidden="true" /> : <ShieldAlert size={22} aria-hidden="true" />}<div><strong>{result.verified ? "Service reports verified" : "Service did not verify this presentation"}</strong><p>{result.status.replace(/_/g, " ")}</p></div></div>}
        {result && <div className="workspace-result-details"><div><span>Verified</span><strong>{result.verified ? "Yes" : "No"}</strong></div>{result.signature_valid !== undefined && <div><span>Signature</span><strong>{result.signature_valid ? "Valid" : "Invalid"}</strong></div>}{result.challenge_valid !== undefined && <div><span>Challenge</span><strong>{result.challenge_valid ? "Valid" : "Invalid"}</strong></div>}{elapsedMs !== null && <div><span>Service round trip</span><strong>{elapsedMs.toFixed(1)} ms</strong></div>}</div>}
        {result?.errors.length ? <ul className="workspace-result-errors" aria-label="Service reported errors">{result.errors.map((item, index) => <li key={index}>{item}</li>)}</ul> : null}
      </section>
    </main>
  );
};
