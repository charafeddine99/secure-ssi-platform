import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, FileCheck2, History, Search, ShieldCheck } from "lucide-react";

export const VerifierDashboard: React.FC = () => (
  <main className="workspace-page verifier-dashboard">
    <header className="workspace-page-header verifier-dashboard-header">
      <div>
        <p className="workspace-eyebrow">Verification workspace</p>
        <h1>Verify credentials with confidence</h1>
        <p>Create a holder request or validate a presentation with the Identity Service.</p>
      </div>
      <span className="verifier-protocol-label"><ShieldCheck size={15} aria-hidden="true" /> OID4VP · DCQL</span>
    </header>

    <section className="verifier-workflow" aria-label="Verification workflow">
      <div className="verifier-workflow__intro">
        <p className="workspace-eyebrow">How it works</p>
        <h2>A clear, consent-led flow</h2>
        <p>Every outcome comes from the connected verification service.</p>
      </div>
      <ol>
        <li><span>01</span><div><strong>Make a request</strong><small>Explain why you need the credential.</small></div></li>
        <li><span>02</span><div><strong>Holder reviews</strong><small>The holder chooses whether to share.</small></div></li>
        <li><span>03</span><div><strong>Service verifies</strong><small>Use the returned policy result.</small></div></li>
      </ol>
    </section>

    <section className="verifier-task-grid" aria-label="Available verification tasks">
      <Link className="verifier-task-card verifier-task-card--primary" to="/verifier/request">
        <span className="verifier-task-card__icon"><FileCheck2 size={22} aria-hidden="true" /></span>
        <span className="verifier-task-card__copy"><small>OID4VP · QR request</small><strong>Create a presentation request</strong><span>Set a purpose and the supported credential fields, then create a real wallet request.</span></span>
        <span className="verifier-task-card__action">Create request <ArrowRight size={16} aria-hidden="true" /></span>
      </Link>
      <Link className="verifier-task-card" to="/verifier/verify">
        <span className="verifier-task-card__icon"><Search size={22} aria-hidden="true" /></span>
        <span className="verifier-task-card__copy"><small>Manual verification</small><strong>Verify a presentation</strong><span>Submit a presentation with the challenge and domain from its request.</span></span>
        <span className="verifier-task-card__action">Verify presentation <ArrowRight size={16} aria-hidden="true" /></span>
      </Link>
    </section>

    <section className="workspace-panel verifier-history-availability" aria-labelledby="verifier-history-title">
      <span className="workspace-icon-tile"><History size={20} aria-hidden="true" /></span>
      <div><h2 id="verifier-history-title">Verification history</h2><p>The current API does not provide a history list for this account. Individual request outcomes remain available in their active session.</p></div>
      <Link className="workspace-text-action" to="/verifier/history">Details <ArrowRight size={16} aria-hidden="true" /></Link>
    </section>
  </main>
);
