import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { StatusChip } from "../../components/common/StatusChip";
import { ArrowLeft, Building2, CalendarDays, Check, Copy, QrCode } from "lucide-react";
import { fetchCredentials, type BackendCredential } from "../../services/api";

export const CredentialDetailPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const [credential, setCredential] = useState<BackendCredential | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setCredential(null);
    fetchCredentials()
      .then((credentials) => {
        if (active) setCredential(credentials.find((item) => item.id === id) ?? null);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Could not load credential.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  const handleCopy = async () => {
    if (!credential?.raw_credential) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(credential.raw_credential, null, 2));
      setCopyError(null);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError("The credential data could not be copied. Check clipboard permission in your browser.");
    }
  };

  if (loading || error || !credential) {
    return (
      <main className="holder-page holder-credential-page">
        <header className="holder-page-header">
          <div><p className="holder-page-eyebrow">PERSONAL WALLET</p><h1>Credential details</h1><p>Details are loaded only from your signed-in wallet.</p></div>
        </header>
        <button type="button" className="holder-back-link" onClick={() => navigate("/wallet")}>
          <ArrowLeft size={16} /> Back to Wallet
        </button>
        <section className={`holder-state-panel${error ? " holder-state-panel--error" : ""}`} role={error ? "alert" : "status"}>
          <h2>{loading ? "Loading credential" : error ? "Credential unavailable" : "Credential not found"}</h2>
          <p>{loading ? "Loading credential from your wallet…" : error || "This credential is not available in your wallet."}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="holder-page holder-credential-page">
      <header className="holder-page-header">
        <div>
          <p className="holder-page-eyebrow">PERSONAL WALLET</p>
          <h1>Credential details</h1>
          <p>Review the issuer, status and claims held in your wallet.</p>
        </div>
      </header>
      <button
        type="button"
        className="holder-back-link"
        onClick={() => navigate("/wallet")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          backgroundColor: "transparent",
          border: "none",
          color: "#94a3b8",
          fontSize: "0.85rem",
          cursor: "pointer",
          padding: 0
        }}
      >
        <ArrowLeft size={16} />
        Back to Wallet
      </button>

      <article
        className="holder-credential-detail-card"
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "16px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="holder-credential-detail-title">
            <span style={{ fontSize: "0.7rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase" }}>
              {credential.category} CREDENTIAL
            </span>
            <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#ffffff", margin: "2px 0 0 0" }}>
              {credential.title}
            </h2>
          </div>
          <StatusChip status={credential.status} />
        </div>

        <p className="holder-verification-note" style={{ margin: 0, color: "#fbbf24", fontSize: "0.78rem" }}>
          Stored status is shown here. Use the verifier to evaluate the credential proof.
        </p>

        <dl className="holder-credential-facts">
          <div>
            <dt><Building2 size={15} aria-hidden="true" /> Issued by</dt>
            <dd>{credential.issuer_name || credential.issuer || "Issuer not supplied"}</dd>
            {credential.issuer_name && credential.issuer && <code>{credential.issuer}</code>}
          </div>
          <div><dt><CalendarDays size={15} aria-hidden="true" /> Issued</dt><dd>{credential.issued_date || "Not supplied"}</dd></div>
          <div><dt><CalendarDays size={15} aria-hidden="true" /> Expires</dt><dd>{credential.expiry_date || "Not supplied"}</dd></div>
        </dl>

        {/* Claims Table */}
        <section className="holder-credential-claims" aria-labelledby="holder-claims-title">
          <h2 id="holder-claims-title">Credential claims</h2>
          <div className="holder-credential-claims-grid">
            {Object.entries(credential.claims || {}).length > 0 ? Object.entries(credential.claims || {}).map(([k, v]) => (
              <dl
                key={k}
                className="holder-credential-claim-row"
              >
                <dt>{k}</dt>
                <dd>{typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}</dd>
              </dl>
            )) : <p className="holder-detail-empty">No claim fields were returned for this credential.</p>}
          </div>
        </section>

        <details className="holder-technical-details">
          <summary>Technical proof data (not verified on this page)</summary>
          <p>Stored proof data is not evidence that this credential's signature or status has been verified.</p>
          <code>{credential.proof_value || "No proof value was returned by the wallet service."}</code>
        </details>

        {copyError && <p className="holder-inline-error" role="alert">{copyError}</p>}

        <div className="holder-credential-detail-actions">
          <button
            type="button"
            className="holder-secondary-action"
            onClick={handleCopy}
            disabled={!credential.raw_credential}
            title={credential.raw_credential ? "Copy the original credential returned by the wallet" : "Original serialized credential was not returned by the wallet"}
            style={{
              flex: 1,
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              color: "#e2e8f0",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: credential.raw_credential ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            {copied ? <Check size={16} color="#34d399" /> : <Copy size={16} />}
            {copied ? "Credential copied" : "Copy credential data"}
          </button>

          <button
            type="button"
            className="holder-primary-action"
            onClick={() => navigate("/wallet/scan")}
            style={{
              flex: 1,
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              border: "none",
              color: "#ffffff",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            <QrCode size={16} />
            Use verifier request
          </button>
        </div>
      </article>
    </main>
  );
};
