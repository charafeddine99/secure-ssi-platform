import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useWallet } from "../../context/WalletContext";
import { fetchCredentials, fetchPendingOffers, claimOid4vciOffer, getOrCreateHolderWallet, HolderWallet, Oid4vciOffer } from "../../services/api";
import { CredentialCard, CredentialCardData } from "../../components/credentials/CredentialCard";
import { CredentialDetailModal } from "../../components/credentials/CredentialDetailModal";
import {
  QrCode,
  RefreshCw,
  ShieldCheck,
  AlertCircle,
  Inbox,
  CheckCircle2,
  Clock,
  Building,
  FileCheck,
  Check
} from "lucide-react";

export const WalletDashboard: React.FC = () => {
  const { user } = useAuth();
  const { account } = useWallet();
  const navigate = useNavigate();

  const [credentials, setCredentials] = useState<CredentialCardData[]>([]);
  const [wallet, setWallet] = useState<HolderWallet | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("ALL");
  const [selectedCredForDetail, setSelectedCredForDetail] = useState<CredentialCardData | null>(null);

  // OID4VCI Pending Offers State (Sprint 9 Golden Path)
  const [pendingOffers, setPendingOffers] = useState<Oid4vciOffer[]>([]);
  const [loadingOffers, setLoadingOffers] = useState(false);
  const [offersError, setOffersError] = useState<string | null>(null);
  const [selectedOfferForConsent, setSelectedOfferForConsent] = useState<Oid4vciOffer | null>(null);
  const [pinInput, setPinInput] = useState("");
  const [offerConsent, setOfferConsent] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Load real credentials from backend
  const loadCredentials = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const currentWallet = await getOrCreateHolderWallet();
      setWallet(currentWallet);
      const data = await fetchCredentials(user?.did, account || user?.walletAddress, currentWallet.walletId);
      setCredentials(data.map((d) => ({
        id: d.id,
        title: d.title,
        category: d.category,
        issuer: d.issuer,
        issuerName: d.issuer_name,
        issuedDate: d.issued_date,
        expiryDate: d.expiry_date,
        status: d.status,
        claims: d.claims,
        proofValue: d.proof_value,
        aiRiskScore: d.ai_risk_score ?? undefined,
      })));
    } catch (err: unknown) {
      setCredentials([]);
      setLoadError(err instanceof Error ? err.message : "Could not load wallet data.");
    } finally {
      setLoading(false);
    }
  }, [account, user?.walletAddress, user?.did]);

  // Load pending credential offers from authoritative OID4VCI endpoint
  const loadPendingOffers = useCallback(async () => {
    setLoadingOffers(true);
    setOffersError(null);
    try {
      const offers = await fetchPendingOffers();
      setPendingOffers(offers.filter((o) => o.status === "PENDING"));
    } catch (err: unknown) {
      setPendingOffers([]);
      setOffersError(err instanceof Error ? err.message : "Could not load credential offers.");
    } finally {
      setLoadingOffers(false);
    }
  }, []);

  useEffect(() => {
    loadCredentials();
    loadPendingOffers();
  }, [loadCredentials, loadPendingOffers]);

  const handleSyncAll = async () => {
    await Promise.all([loadCredentials(), loadPendingOffers()]);
  };

  // Open Consent Modal
  const handleOpenConsent = (offer: Oid4vciOffer) => {
    setSelectedOfferForConsent(offer);
    setPinInput("");
    setOfferConsent(false);
    setNotification(null);
  };

  // Explicit user consent claim action (real OID4VCI flow)
  const handleConfirmClaim = async () => {
    if (!selectedOfferForConsent || !offerConsent) return;
    setClaiming(true);
    setNotification(null);
    try {
      const currentWallet = wallet || await getOrCreateHolderWallet();
      const res = await claimOid4vciOffer({
        preAuthorizedCode: selectedOfferForConsent.preAuthorizedCode,
        holderDid: currentWallet.holderDid,
        walletId: currentWallet.walletId,
        credentialConfigurationId: selectedOfferForConsent.credentialConfigurationIds[0],
        userPin: pinInput.trim() || undefined
      });

      // Remove claimed offer from pending list
      setPendingOffers((prev) => prev.filter((o) => o.offerId !== selectedOfferForConsent.offerId));
      setSelectedOfferForConsent(null);
      setNotification({
        type: "success",
        message: `Credential received. Reference: ${res.credentialId}`
      });
      setTimeout(() => setNotification(null), 5000);
      // Immediately reload credentials from database
      await loadCredentials();
    } catch (err: unknown) {
      setNotification({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to claim credential."
      });
    } finally {
      setClaiming(false);
    }
  };

  const categories = ["ALL", "IDENTITY", "QUALIFIED", "FINANCE"];

  const filtered = credentials.filter((c) => {
    if (activeCategory === "ALL") return true;
    return c.category.toUpperCase() === activeCategory;
  });

  return (
    <main className="role-dashboard role-dashboard--holder holder-page holder-wallet-page" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <header className="holder-page-header">
        <div>
          <p className="holder-page-eyebrow">PERSONAL WALLET</p>
          <h1>Your credentials</h1>
          <p>Review credentials issued to your wallet and decide when to share them.</p>
        </div>
        <span className="holder-wallet-count" aria-label={loading ? "Checking wallet" : loadError ? "Wallet unavailable" : `${credentials.length} credentials in wallet`}>
          <ShieldCheck size={17} aria-hidden="true" />
          {loading ? "Checking wallet" : loadError ? "Unavailable" : `${credentials.length} ${credentials.length === 1 ? "credential" : "credentials"}`}
        </span>
      </header>
      {/* Notification Banner */}
      {notification && (
        <div
          role={notification.type === "error" ? "alert" : "status"}
          className={`holder-notice holder-notice--${notification.type}`}
          style={{
            padding: "10px 16px",
            borderRadius: "10px",
            backgroundColor: notification.type === "success" ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
            border: `1px solid ${notification.type === "success" ? "#10b981" : "#ef4444"}`,
            color: notification.type === "success" ? "#6ee7b7" : "#fca5a5",
            fontSize: "0.85rem",
            display: "flex",
            alignItems: "center",
            gap: "8px"
          }}
        >
          {notification.type === "success" ? <Check size={16} /> : <AlertCircle size={16} />}
          <span>{notification.message}</span>
        </div>
      )}

      {offersError && <div className="workspace-error" role="alert">{offersError}</div>}

      {/* Quick Action Bar */}
      <section
        className="holder-wallet-toolbar"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          backgroundColor: "#111827",
          padding: "12px 16px",
          borderRadius: "14px",
          border: "1px solid #1f2937"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <ShieldCheck size={18} color="#34d399" />
          <span className="holder-wallet-state" aria-live="polite">
            {loading ? "Loading your wallet" : loadError ? "Wallet unavailable" : "Wallet ready"}
          </span>
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            type="button"
            onClick={handleSyncAll}
            disabled={loading || loadingOffers}
            title="Refresh wallet data"
            style={{
              padding: "6px 10px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              color: "#94a3b8",
              border: "1px solid #374151",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px"
            }}
          >
            <RefreshCw size={14} className={loading || loadingOffers ? "spin" : ""} />
            Sync
          </button>

          <button
            onClick={() => navigate("/wallet/scan")}
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px"
            }}
          >
            <QrCode size={14} aria-hidden="true" />
            Open request
          </button>
        </div>
      </section>

      {/* Pending Credential Offers Section (OID4VCI Golden Path) */}
      {pendingOffers.length > 0 && (
        <section
          className="holder-offers-section"
          style={{
            backgroundColor: "#111827",
            borderRadius: "14px",
            border: "1px solid #3b82f6",
            padding: "16px",
            boxShadow: "0 0 15px rgba(59, 130, 246, 0.15)"
          }}
        >
          <div
            className="holder-offers-heading"
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "12px"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Inbox size={20} color="#60a5fa" />
              <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
                Pending Credential Offers ({pendingOffers.length})
              </h3>
            </div>
            <span
              style={{
                fontSize: "0.7rem",
                padding: "3px 8px",
                borderRadius: "6px",
                backgroundColor: "rgba(59, 130, 246, 0.2)",
                color: "#93c5fd",
                fontWeight: 600,
                textTransform: "uppercase"
              }}
            >
              Action Required
            </span>
          </div>

          <div className="holder-offers-list" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {pendingOffers.map((offer) => (
              <div
                key={offer.offerId}
                className="holder-offer-card"
                style={{
                  backgroundColor: "#1e293b",
                  borderRadius: "10px",
                  border: "1px solid #334155",
                  padding: "14px"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Building size={14} color="#94a3b8" />
                      <span style={{ fontSize: "0.75rem", color: "#94a3b8", fontWeight: 500 }}>
                        {offer.credentialIssuer || "Issuer not supplied"}
                      </span>
                    </div>
                    <h4 style={{ margin: "4px 0 0 0", fontSize: "0.9rem", color: "#f8fafc", fontWeight: 600 }}>
                      {offer.credentialConfigurationIds.join(", ")}
                    </h4>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.7rem", color: "#f59e0b" }}>
                    <Clock size={12} />
                    <span>Expires: {new Date(offer.expiresAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                </div>

                {/* Claims Preview */}
                {offer.subjectData && Object.keys(offer.subjectData).length > 0 && (
                  <div
                    style={{
                      backgroundColor: "#0f172a",
                      borderRadius: "6px",
                      padding: "8px 10px",
                      margin: "8px 0 12px 0",
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: "6px",
                      fontSize: "0.75rem"
                    }}
                  >
                    {Object.entries(offer.subjectData).map(([k, v]) => (
                      <div key={k} style={{ color: "#cbd5e1" }}>
                        <span style={{ color: "#64748b" }}>{k}: </span>
                        <strong style={{ color: "#e2e8f0" }}>{String(v)}</strong>
                      </div>
                    ))}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="holder-offer-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                  <button
                    type="button"
                    className="holder-primary-action"
                    onClick={() => handleOpenConsent(offer)}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "6px",
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      border: "none",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px"
                    }}
                  >
                    <CheckCircle2 size={14} />
                    Review & Accept
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Category Pills */}
      <div className="holder-category-filters" role="group" aria-label="Filter credentials by category" style={{ display: "flex", gap: "6px", overflowX: "auto", paddingBottom: "4px" }}>
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            aria-pressed={activeCategory === cat}
            className={activeCategory === cat ? "is-active" : undefined}
            onClick={() => setActiveCategory(cat)}
            style={{
              padding: "6px 14px",
              borderRadius: "9999px",
              fontSize: "0.75rem",
              fontWeight: 600,
              border: "none",
              cursor: "pointer",
              backgroundColor: activeCategory === cat ? "#2563eb" : "#111827",
              color: activeCategory === cat ? "#ffffff" : "#94a3b8",
              transition: "all 0.15s ease"
            }}
          >
            {cat === "ALL" ? "All Credentials" : cat}
          </button>
        ))}
      </div>

      {/* Credential Cards List */}
      <section className="holder-credentials-section" aria-label="Credentials in your wallet">
        <div className="holder-credentials-heading">
          <div>
            <h2>My credentials</h2>
            <p>Only credentials available in your signed-in wallet are shown.</p>
          </div>
        </div>
        <div className="holder-credentials-grid">
          {filtered.map((cred) => (
          <CredentialCard
            key={cred.id}
            credential={cred}
            onViewDetails={(c) => setSelectedCredForDetail(c)}
            onPresent={() => navigate("/wallet/scan")}
          />
        ))}

        {filtered.length === 0 && (
          <div
            className={`holder-empty-state${loadError ? " holder-empty-state--error" : ""}`}
            role={loading ? "status" : loadError ? "alert" : "status"}
            style={{
              textAlign: "center",
              padding: "40px 20px",
              backgroundColor: "#111827",
              borderRadius: "14px",
              border: "1px solid #1f2937",
              color: "#94a3b8"
            }}
          >
            <AlertCircle size={32} color="#64748b" style={{ margin: "0 auto 10px auto" }} aria-hidden="true" />
            <h3>{loading ? "Loading your wallet" : loadError ? "Wallet could not be loaded" : credentials.length === 0 ? "No credentials yet" : "No credentials in this category"}</h3>
            <p style={{ margin: 0, fontSize: "0.9rem" }}>
              {loading ? "Loading credentials from your wallet…" : loadError || (credentials.length === 0 ? "Credentials issued to this wallet will appear here." : "Choose another category to view your wallet credentials.")}
            </p>
          </div>
        )}
        </div>
      </section>

      {/* Explicit Consent Modal for OID4VCI Offer Claim */}
      {selectedOfferForConsent && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(4px)"
          }}
        >
          <div
            className="holder-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="holder-offer-dialog-title"
            style={{
              backgroundColor: "#111827",
              border: "1px solid #1f2937",
              borderRadius: "16px",
              padding: "24px",
              width: "100%",
              maxWidth: "500px",
              color: "#f8fafc",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <FileCheck size={24} color="#3b82f6" />
              <h3 id="holder-offer-dialog-title" style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700 }}>
                Review credential offer
              </h3>
            </div>

            <p style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "16px", lineHeight: "1.4" }}>
              Review the issuer and the information included in this offer before asking the issuer to issue a credential to your wallet.
            </p>

            <div style={{ backgroundColor: "#1f2937", padding: "12px", borderRadius: "10px", marginBottom: "16px" }}>
              <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>Issuing Authority:</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc", marginBottom: "10px" }}>
                {selectedOfferForConsent.credentialIssuer}
              </div>

              <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>Credential Profile:</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#38bdf8", marginBottom: "10px" }}>
                {selectedOfferForConsent.credentialConfigurationIds.join(", ")}
              </div>

              <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>Binding Holder DID:</div>
              <div style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "#a7f3d0", wordBreak: "break-all" }}>
                {wallet?.holderDid || "Holder wallet unavailable"}
              </div>
            </div>

            {/* Claims Table */}
            <div style={{ marginBottom: "16px" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#cbd5e1", marginBottom: "6px" }}>
                Credential Claims to be Bound:
              </div>
              <div style={{ maxHeight: "150px", overflowY: "auto", border: "1px solid #374151", borderRadius: "8px" }}>
                {Object.entries(selectedOfferForConsent.subjectData || {}).map(([key, val], idx) => (
                  <div
                    key={key}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "6px 10px",
                      fontSize: "0.75rem",
                      backgroundColor: idx % 2 === 0 ? "#111827" : "#1a2234",
                      borderBottom: "1px solid #2d3748"
                    }}
                  >
                    <span style={{ color: "#94a3b8" }}>{key}</span>
                    <span style={{ fontWeight: 600, color: "#f8fafc" }}>{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* PIN Input if required */}
            <div style={{ marginBottom: "16px" }}>
              <label htmlFor="holder-wallet-offer-pin" style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                User PIN (if provided by issuer):
              </label>
              <input
                id="holder-wallet-offer-pin"
                type="password"
                placeholder="Enter PIN if required"
                value={pinInput}
                onChange={(e) => setPinInput(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  color: "#f8fafc",
                  fontSize: "0.85rem",
                  boxSizing: "border-box"
                }}
              />
            </div>

            {/* Consent Disclaimer */}
            <div
              style={{
                backgroundColor: "rgba(16, 185, 129, 0.1)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                padding: "8px 12px",
                borderRadius: "8px",
                fontSize: "0.75rem",
                color: "#6ee7b7",
                marginBottom: "16px"
              }}
            >
              This is an offer only. No credential is stored until you confirm acceptance and the issuer returns a credential successfully.
            </div>

            <label className="holder-offer-consent">
              <input
                type="checkbox"
                checked={offerConsent}
                onChange={(event) => setOfferConsent(event.target.checked)}
              />
              <span>I reviewed the issuer, credential type and claims above, and want to accept this offer.</span>
            </label>

            {/* Modal Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                onClick={() => setSelectedOfferForConsent(null)}
                disabled={claiming}
                style={{
                  padding: "8px 16px",
                  borderRadius: "8px",
                  backgroundColor: "#1f2937",
                  color: "#94a3b8",
                  border: "1px solid #374151",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmClaim}
                disabled={claiming || !offerConsent}
                style={{
                  padding: "8px 20px",
                  borderRadius: "8px",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: claiming || !offerConsent ? "not-allowed" : "pointer",
                  opacity: offerConsent ? 1 : 0.58,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                {claiming ? <RefreshCw size={14} className="spin" /> : <CheckCircle2 size={14} />}
                {claiming ? "Claiming..." : "Accept & Claim"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      <CredentialDetailModal
        credential={selectedCredForDetail}
        isOpen={!!selectedCredForDetail}
        onClose={() => setSelectedCredForDetail(null)}
      />

    </main>
  );
};
