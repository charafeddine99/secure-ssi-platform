import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, BadgeCheck, FileCode2, RefreshCw } from "lucide-react";
import { fetchOid4vciIssuerMetadata, type Oid4vciIssuerMetadata } from "../../services/api";

type MetadataState = "loading" | "ready" | "error";

const valuesOrFallback = (values?: string[]) => values?.length ? values : ["Not reported"];

export const CredentialTemplatesPage: React.FC = () => {
  const navigate = useNavigate();
  const [metadata, setMetadata] = useState<Oid4vciIssuerMetadata | null>(null);
  const [state, setState] = useState<MetadataState>("loading");
  const [error, setError] = useState<string | null>(null);

  const loadMetadata = useCallback(async () => {
    setState("loading");
    setError(null);
    try {
      setMetadata(await fetchOid4vciIssuerMetadata());
      setState("ready");
    } catch (cause) {
      setMetadata(null);
      setError(cause instanceof Error ? cause.message : "Issuer metadata could not be loaded.");
      setState("error");
    }
  }, []);

  useEffect(() => { void loadMetadata(); }, [loadMetadata]);

  const configurations = Object.entries(metadata?.credential_configurations_supported || {});

  return (
    <main className="workspace-page issuer-page issuer-configurations-page">
      <header className="workspace-page-header issuer-page-header">
        <div>
          <p className="workspace-eyebrow">OID4VCI metadata</p>
          <h1>Credential configurations</h1>
          <p>A read-only catalogue of credential profiles currently published by the issuer metadata endpoint.</p>
        </div>
        <div className="workspace-header-actions issuer-page-actions">
          <button type="button" className="workspace-secondary-action" onClick={() => void loadMetadata()} disabled={state === "loading"}>
            <RefreshCw size={16} aria-hidden="true" className={state === "loading" ? "spin" : undefined} /> Refresh metadata
          </button>
        </div>
      </header>

      {state === "ready" && metadata && (
        <section className="issuer-metadata-source" aria-label="Metadata source">
          <span className="issuer-metadata-source__icon"><BadgeCheck size={18} aria-hidden="true" /></span>
          <div><strong>Published issuer metadata</strong><code>{metadata.credential_issuer}</code></div>
          <span className="issuer-record-count">{configurations.length} {configurations.length === 1 ? "configuration" : "configurations"}</span>
        </section>
      )}

      {state === "loading" && (
        <section className="issuer-data-state" role="status" aria-busy="true">
          <span className="issuer-loading-mark" aria-hidden="true"><RefreshCw size={17} /></span>
          <div><strong>Loading published configurations</strong><p>Requesting the current OID4VCI metadata document.</p></div>
        </section>
      )}

      {state === "error" && (
        <section className="issuer-data-state issuer-data-state--error" role="alert">
          <span className="issuer-loading-mark" aria-hidden="true"><FileCode2 size={18} /></span>
          <div className="issuer-data-state__copy"><strong>Issuer metadata is unavailable</strong><p>{error}</p></div>
          <button type="button" className="workspace-secondary-action" onClick={() => void loadMetadata()}>Retry</button>
        </section>
      )}

      {state === "ready" && configurations.length === 0 && (
        <section className="issuer-data-state issuer-data-state--empty">
          <span className="issuer-loading-mark" aria-hidden="true"><FileCode2 size={18} /></span>
          <div><strong>No configurations published</strong><p>The metadata document was loaded successfully but contains no supported credential configurations.</p></div>
        </section>
      )}

      {state === "ready" && configurations.length > 0 && (
        <section className="issuer-config-grid" aria-label="Supported credential configurations">
          {configurations.map(([configurationId, configuration]) => {
            const displayName = configuration.display?.find((item) => item.name)?.name || configurationId;
            const proofTypes = Object.entries(configuration.proof_types_supported || {});
            const proofAlgorithms = [...new Set(proofTypes.flatMap(([, proof]) => proof.proof_signing_alg_values_supported || []))];
            const detailsId = `configuration-details-${configurationId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
            return (
              <article className="workspace-panel issuer-config-card" key={configurationId}>
                <div className="issuer-config-card__header">
                  <span className="issuer-config-card__icon"><FileCode2 size={20} aria-hidden="true" /></span>
                  <div className="issuer-config-card__title">
                    <p className="workspace-eyebrow">Published profile</p>
                    <h2>{displayName}</h2>
                  </div>
                </div>
                <code className="issuer-config-id">{configurationId}</code>
                <dl className="issuer-config-facts">
                  <div><dt>Format</dt><dd>{configuration.format || "Not reported"}</dd></div>
                  <div><dt>Binding methods</dt><dd>{valuesOrFallback(configuration.cryptographic_binding_methods_supported).join(", ")}</dd></div>
                  <div><dt>Credential signing</dt><dd>{valuesOrFallback(configuration.credential_signing_alg_values_supported).join(", ")}</dd></div>
                  <div><dt>Proof types</dt><dd>{proofTypes.length ? proofTypes.map(([name]) => name).join(", ") : "Not reported"}</dd></div>
                </dl>
                <details className="issuer-config-details" id={detailsId}>
                  <summary>View supported proof algorithms</summary>
                  {proofAlgorithms.length ? (
                    <ul>{proofAlgorithms.map((algorithm) => <li key={algorithm}><code>{algorithm}</code></li>)}</ul>
                  ) : (
                    <p>The metadata does not report proof signing algorithms for this configuration.</p>
                  )}
                  {configuration.scope && <p>Scope: <code>{configuration.scope}</code></p>}
                </details>
                <button
                  type="button"
                  className="workspace-primary-action issuer-config-action"
                  onClick={() => navigate(`/issuer/issue?credentialConfigurationId=${encodeURIComponent(configurationId)}`)}
                >
                  Create offer with this profile <ArrowRight size={16} aria-hidden="true" />
                </button>
              </article>
            );
          })}
        </section>
      )}

      <p className="issuer-catalogue-note">This catalogue reflects metadata only. It does not create, edit or delete credential schemas.</p>
    </main>
  );
};
