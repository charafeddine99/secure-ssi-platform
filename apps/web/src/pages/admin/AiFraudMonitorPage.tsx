import React, { useEffect, useState } from "react";
import { AlertTriangle, Cpu, RefreshCw } from "lucide-react";
import { fetchFraudStats, FraudModelStats } from "../../services/api";

function readableStatus(value: string | undefined): string {
  if (!value) return "Not reported";
  return value
    .replace(/^\[|\]$/g, "")
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/(^|[\s/])[a-z]/g, (part) => part.toUpperCase());
}

export const AiFraudMonitorPage: React.FC = () => {
  const [stats, setStats] = useState<FraudModelStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      setStats(await fetchFraudStats());
    } catch (cause) {
      setStats(null);
      setError(cause instanceof Error ? cause.message : "Risk service status is unavailable.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadStats(); }, []);

  return (
    <main className="workspace-page">
      <header className="workspace-page-header">
        <div>
          <p className="workspace-eyebrow">Platform operations</p>
          <h1>Risk evaluation service</h1>
          <p>Risk service status and configured inputs.</p>
        </div>
        <button type="button" className="workspace-secondary-action" onClick={() => void loadStats()} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spin" : ""} /> Refresh
        </button>
      </header>

      {error && <div className="workspace-error" role="alert"><AlertTriangle size={17} /> {error}</div>}
      {loading ? <section className="workspace-empty-panel" role="status">Loading risk service metadata…</section> : !stats ? (
        <section className="workspace-empty-panel"><p>Risk service metadata is unavailable.</p></section>
      ) : (
        <>
          <section className="workspace-grid workspace-grid--metrics" aria-label="Risk service details">
            <article className="workspace-panel workspace-metric-card"><span>Engine</span><strong>{readableStatus(stats.model_type)}</strong><small>Version: {stats.model_version || "Not reported"}</small></article>
            <article className="workspace-panel workspace-metric-card"><span>Model status</span><strong>{readableStatus(stats.model_status)}</strong><small>Evaluation: {readableStatus(stats.evaluation_status)}</small></article>
            <article className="workspace-panel workspace-metric-card"><span>Data scope</span><strong>{readableStatus(stats.dataset_label)}</strong><small>Advisory only: {stats.advisory_only ? "Yes" : "Not confirmed"}</small></article>
          </section>
          <section className="workspace-panel">
            <div className="workspace-section-heading"><div><p className="workspace-eyebrow"><Cpu size={14} /> Risk service</p><h2>Reported signals</h2></div></div>
            {stats.risk_signals.length ? (
              <ul className="workspace-signal-list">{stats.risk_signals.map((signal) => <li key={signal}>{readableStatus(signal)}</li>)}</ul>
            ) : <p className="workspace-footnote">No signals were reported by the service.</p>}
            <p className="workspace-footnote">Risk output cannot establish issuer trust, credential validity, or active status-list state.</p>
          </section>
        </>
      )}
      <aside className="workspace-notice">
        <strong>Advisory service</strong>
        <span>Risk output does not replace credential or status checks.</span>
      </aside>
    </main>
  );
};
