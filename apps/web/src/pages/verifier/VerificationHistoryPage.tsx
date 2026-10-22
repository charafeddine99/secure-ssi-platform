import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, History, Info } from "lucide-react";

export const VerificationHistoryPage: React.FC = () => (
  <main className="workspace-page verifier-history-page">
    <Link className="workspace-text-action verifier-back-link" to="/verifier"><ArrowLeft size={16} aria-hidden="true" /> Verifier workspace</Link>
    <header className="workspace-page-header">
      <div><p className="workspace-eyebrow">Verifier</p><h1>Verification history</h1><p>History records are shown only when the service provides them for this account.</p></div>
    </header>

    <section className="workspace-empty-panel verifier-history-unavailable" role="status" aria-labelledby="history-unavailable-title">
      <span className="workspace-empty-icon"><History size={23} aria-hidden="true" /></span>
      <p className="workspace-eyebrow">Data source unavailable</p>
      <h2 id="history-unavailable-title">No history endpoint is available</h2>
      <p>The current API does not return a verifier history list. No records have been inferred or displayed as an empty history.</p>
      <div className="workspace-notice verifier-history-notice"><Info size={17} aria-hidden="true" /><span>When a session is open, its current outcome is available from the request screen. This page cannot retrieve past sessions.</span></div>
      <div className="verifier-history-actions">
        <Link className="workspace-primary-action" to="/verifier/request">Create a request <ArrowRight size={16} aria-hidden="true" /></Link>
        <Link className="workspace-secondary-action" to="/verifier">Return to workspace</Link>
      </div>
    </section>
  </main>
);
