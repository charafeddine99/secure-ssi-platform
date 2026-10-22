import React, { useCallback, useEffect, useRef, useState } from "react";
import { Building2, FileCheck2, RefreshCw, TriangleAlert } from "lucide-react";
import { StatusChip } from "../../components/common/StatusChip";
import {
  fetchOid4vciIssuerMetadata,
  fetchPublicTrustedIssuers,
  Oid4vciIssuerMetadata,
  PublicTrustRecord,
} from "../../services/api";

export const EcosystemPage: React.FC = () => {
  const [metadata, setMetadata] = useState<Oid4vciIssuerMetadata | null>(null);
  const [issuers, setIssuers] = useState<PublicTrustRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [issuersError, setIssuersError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  const loadDirectory = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    const [metadataResult, issuersResult] = await Promise.allSettled([
      fetchOid4vciIssuerMetadata(controller.signal),
      fetchPublicTrustedIssuers(controller.signal),
    ]);

    if (controller.signal.aborted || activeRequest.current !== controller) return;

    if (metadataResult.status === "fulfilled") {
      setMetadata(metadataResult.value);
      setMetadataError(null);
    } else {
      setMetadata(null);
      setMetadataError(
        metadataResult.reason instanceof Error
          ? metadataResult.reason.name === "TimeoutError"
            ? "The credential metadata service did not respond within 10 seconds."
            : metadataResult.reason.message
          : "Credential metadata is unavailable.",
      );
    }

    if (issuersResult.status === "fulfilled") {
      setIssuers(issuersResult.value.filter((issuer) => {
        const source = issuer.trustSource?.toUpperCase() || "";
        const seededFixture = issuer.auditMetadata?.seeded === true || issuer.auditMetadata?.environment === "DEMO_LAB";
        return !seededFixture && !source.startsWith("DEMO_") && !source.startsWith("LOCAL_TEST_");
      }));
      setIssuersError(null);
    } else {
      setIssuers([]);
      setIssuersError(
        issuersResult.reason instanceof Error
          ? issuersResult.reason.name === "TimeoutError"
            ? "The issuer registry did not respond within 10 seconds."
            : issuersResult.reason.message
          : "The issuer registry is unavailable.",
      );
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void loadDirectory();
    return () => activeRequest.current?.abort();
  }, [loadDirectory]);

  const configurations = Object.entries(metadata?.credential_configurations_supported || {});
  const formatDate = (value?: string | null) => {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? null : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
  };

  const issuerError = (message: string) => (
    <div className="public-directory-error" role="alert">
      <strong><TriangleAlert size={16} aria-hidden="true" /> Data could not be loaded</strong>
      <p>{message}</p>
      <button type="button" onClick={() => void loadDirectory()}>Try again</button>
    </div>
  );

  return (
    <main className="public-directory-page">
      <header className="workspace-page-header">
        <div>
          <p className="workspace-eyebrow">Public directory</p>
          <h1>Issuers and credentials</h1>
          <p>View issuer registrations and credential formats published by this platform.</p>
        </div>
        <button type="button" className="workspace-secondary-action" onClick={() => void loadDirectory()} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spin" : ""} aria-hidden="true" />
          {loading ? "Refreshing" : "Refresh"}
        </button>
      </header>

      <section className="public-directory-section">
        <div className="workspace-section-heading">
          <div><p className="workspace-eyebrow">Trust registry</p><h2>Registered issuers</h2></div>
          <span className="workspace-count" aria-live="polite">{loading ? "Loading" : issuers.length}</span>
        </div>
        {loading ? <div className="workspace-empty-panel" role="status">Loading issuer records…</div> : issuersError ? issuerError(issuersError) : issuers.length === 0 ? (
          <div className="workspace-empty-panel public-directory-empty"><Building2 size={22} /><p>No issuer registrations are published.</p></div>
        ) : (
          <div className="public-directory-list">
            {issuers.map((issuer) => (
              <article className="workspace-panel public-issuer-card" key={issuer.id}>
                <div className="workspace-icon-tile"><Building2 size={19} /></div>
                <div className="public-issuer-card__content">
                  <div className="public-issuer-card__title"><h3>{issuer.organizationName.trim() || "Issuer name not provided"}</h3><StatusChip status={issuer.trustStatus} size="sm" /></div>
                  <code>{issuer.issuerDid.trim() || "Issuer DID not published"}</code>
                  <p>Credential types: {issuer.permittedCredentialTypes.join(", ") || "Not specified"}</p>
                  <small>
                    {formatDate(issuer.validFrom) ? `Valid from ${formatDate(issuer.validFrom)}` : "Start date not reported"}
                    {issuer.validUntil ? ` · Valid through ${formatDate(issuer.validUntil) || "date unavailable"}` : " · No end date reported"}
                  </small>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="public-directory-section">
        <div className="workspace-section-heading">
          <div><p className="workspace-eyebrow">Issuer metadata</p><h2>Credential formats</h2></div>
          <span className="workspace-count" aria-live="polite">{loading ? "Loading" : configurations.length}</span>
        </div>
        {loading ? <div className="workspace-empty-panel" role="status">Loading credential formats…</div> : metadataError ? issuerError(metadataError) : configurations.length === 0 ? (
          <div className="workspace-empty-panel public-directory-empty"><FileCheck2 size={22} /><p>No credential formats are published.</p></div>
        ) : (
          <div className="workspace-grid">
            {configurations.map(([id, configuration]) => (
              <article className="workspace-panel workspace-config-card" key={id}>
                <div className="workspace-config-card__heading">
                  <div className="workspace-icon-tile"><FileCheck2 size={19} /></div>
                  <div><h3>{configuration.display?.find((item) => item.name)?.name || id}</h3><code>{id}</code></div>
                </div>
                <dl className="workspace-config-details">
                  <div><dt>Format</dt><dd>{configuration.format || "Not specified"}</dd></div>
                  <div><dt>Key binding</dt><dd>{configuration.cryptographic_binding_methods_supported?.join(", ") || "Not specified"}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
};
