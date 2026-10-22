import React from "react";
import { ArrowLeft, Clock, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

export const ActivityHistoryPage: React.FC = () => (
  <main className="holder-page holder-activity-page">
    <header className="holder-page-header">
      <div>
        <p className="holder-page-eyebrow">PERSONAL WALLET</p>
        <h1>Activity</h1>
        <p>Review of your credential and sharing history is not available yet.</p>
      </div>
    </header>
    <section className="holder-state-panel holder-state-panel--unavailable" aria-labelledby="holder-activity-unavailable-title">
      <span className="holder-state-panel__icon"><Clock size={22} aria-hidden="true" /></span>
      <div>
        <p className="holder-page-eyebrow">NOT AVAILABLE</p>
        <h2 id="holder-activity-unavailable-title">Personal activity feed unavailable</h2>
        <p>The platform does not currently provide a wallet-scoped event history. This is not an empty activity feed; administrator audit records are not shown here.</p>
      </div>
      <div className="holder-privacy-note"><ShieldCheck size={17} aria-hidden="true" /><span>Your wallet view does not expose platform-wide audit data.</span></div>
      <Link className="holder-primary-action" to="/wallet"><ArrowLeft size={16} aria-hidden="true" /> Return to wallet</Link>
    </section>
  </main>
);
