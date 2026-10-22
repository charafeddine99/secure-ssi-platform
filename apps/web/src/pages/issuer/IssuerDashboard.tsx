import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, FileText, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { fetchIssuerOffers, type Oid4vciOffer } from "../../services/api";
import { StatusChip } from "../../components/common/StatusChip";

type OffersState = "loading" | "ready" | "error";

const formatExpiry = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not supplied" : date.toLocaleString();
};

export const IssuerDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [offers, setOffers] = useState<Oid4vciOffer[]>([]);
  const [state, setState] = useState<OffersState>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadOffers = useCallback(async () => {
    setState("loading");
    setLoadError(null);
    try {
      setOffers(await fetchIssuerOffers());
      setState("ready");
    } catch (error) {
      setOffers([]);
      setLoadError(error instanceof Error ? error.message : "Could not load credential offers.");
      setState("error");
    }
  }, []);

  useEffect(() => { void loadOffers(); }, [loadOffers]);

  const pendingCount = useMemo(
    () => offers.filter((offer) => offer.status.toUpperCase() === "PENDING").length,
    [offers],
  );
  const visibleOffers = offers.slice(0, 10);

  return (
    <main className="workspace-page issuer-page issuer-dashboard">
      <header className="workspace-page-header issuer-page-header">
        <div>
          <p className="workspace-eyebrow">Issuer workspace</p>
          <h1>Issuance overview</h1>
          <p>Manage credential offer configurations, create new offers and review their latest service-reported status.</p>
        </div>
        <div className="workspace-header-actions issuer-page-actions">
          <button className="workspace-secondary-action" type="button" onClick={() => void loadOffers()} disabled={state === "loading"}>
            <RefreshCw size={16} aria-hidden="true" className={state === "loading" ? "spin" : undefined} />
            Refresh offers
          </button>
          <button className="workspace-primary-action" type="button" onClick={() => navigate("/issuer/issue")}>
            <Plus size={17} aria-hidden="true" />
            Create offer
          </button>
        </div>
      </header>

      <section className="issuer-overview-strip" aria-label="Issuer account scope">
        <span className="issuer-overview-strip__icon"><ShieldCheck size={18} aria-hidden="true" /></span>
        <div>
          <strong>Issuer account records</strong>
          <p>Offers shown here are returned by the Identity Service for the authenticated issuer. Access scope is enforced by the service.</p>
        </div>
        <button type="button" className="issuer-overview-strip__link" onClick={() => navigate("/issuer/templates")}>
          View configurations <ArrowRight size={15} aria-hidden="true" />
        </button>
      </section>

      <section className="workspace-metrics issuer-metrics" aria-label="Credential offer summary" aria-busy={state === "loading"}>
        <article className={`workspace-metric-card issuer-metric-card${state === "loading" ? " is-loading" : ""}`}>
          <span>Offers returned</span>
          <strong>{state === "loading" ? "Loading" : state === "error" ? "Unavailable" : offers.length}</strong>
          <small>Offers in this issuer account response</small>
        </article>
        <article className={`workspace-metric-card issuer-metric-card${state === "loading" ? " is-loading" : ""}`}>
          <span>Pending claims</span>
          <strong>{state === "loading" ? "Loading" : state === "error" ? "Unavailable" : pendingCount}</strong>
          <small>Offers whose current status is pending</small>
        </article>
      </section>

      <section className="workspace-panel issuer-offers-panel" aria-labelledby="issuer-offers-title" aria-busy={state === "loading"}>
        <div className="workspace-panel-header issuer-offers-heading">
          <div>
            <p className="workspace-eyebrow">Offer activity</p>
            <h2 id="issuer-offers-title">Recent credential offers</h2>
            <p>Up to ten offers returned by the authenticated issuer endpoint.</p>
          </div>
          <span className="issuer-record-count">{state === "ready" ? `${visibleOffers.length} shown` : state === "loading" ? "Loading" : "Unavailable"}</span>
        </div>

        {state === "loading" && (
          <div className="issuer-data-state" role="status">
            <span className="issuer-loading-mark" aria-hidden="true"><RefreshCw size={17} /></span>
            <div><strong>Loading issuer offers</strong><p>Waiting for the authenticated Identity Service response.</p></div>
          </div>
        )}

        {state === "error" && (
          <div className="issuer-data-state issuer-data-state--error" role="alert">
            <span className="issuer-loading-mark" aria-hidden="true"><ShieldCheck size={18} /></span>
            <div className="issuer-data-state__copy"><strong>Offers could not be loaded</strong><p>{loadError}</p></div>
            <button type="button" className="workspace-secondary-action" onClick={() => void loadOffers()}>Try again</button>
          </div>
        )}

        {state === "ready" && offers.length === 0 && (
          <div className="issuer-data-state issuer-data-state--empty">
            <span className="issuer-loading-mark" aria-hidden="true"><FileText size={18} /></span>
            <div><strong>No credential offers returned</strong><p>Create an offer to start a holder claim flow. A created offer is not yet an issued credential.</p></div>
            <button type="button" className="workspace-primary-action" onClick={() => navigate("/issuer/issue")}><Plus size={16} aria-hidden="true" /> Create offer</button>
          </div>
        )}

        {state === "ready" && offers.length > 0 && (
          <>
            <div className="workspace-table-wrap issuer-offers-desktop">
              <table className="workspace-table issuer-offers-table">
                <thead>
                  <tr>
                    <th scope="col">Offer ID</th>
                    <th scope="col">Credential configuration</th>
                    <th scope="col">Service status</th>
                    <th scope="col">Offer expiry</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleOffers.map((offer) => (
                    <tr key={offer.offerId}>
                      <td><code className="issuer-offer-id">{offer.offerId}</code></td>
                      <td>{offer.credentialConfigurationIds.length ? offer.credentialConfigurationIds.join(", ") : "Not supplied"}</td>
                      <td><StatusChip status={offer.status} size="sm" /></td>
                      <td>{offer.expiresAt ? formatExpiry(offer.expiresAt) : "Not supplied"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="issuer-offers-mobile" aria-label="Recent credential offers">
              {visibleOffers.map((offer) => (
                <li className="issuer-offer-card" key={offer.offerId}>
                  <div className="issuer-offer-card__top"><span>Offer</span><StatusChip status={offer.status} size="sm" /></div>
                  <code className="issuer-offer-id">{offer.offerId}</code>
                  <dl>
                    <div><dt>Configuration</dt><dd>{offer.credentialConfigurationIds.join(", ") || "Not supplied"}</dd></div>
                    <div><dt>Expires</dt><dd>{offer.expiresAt ? formatExpiry(offer.expiresAt) : "Not supplied"}</dd></div>
                  </dl>
                </li>
              ))}
            </ul>
            {offers.length > visibleOffers.length && <p className="issuer-list-footnote">Showing the first {visibleOffers.length} of {offers.length} offers returned.</p>}
          </>
        )}
      </section>
    </main>
  );
};
