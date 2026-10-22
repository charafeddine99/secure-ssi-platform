import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  claimOid4vciOffer,
  getOrCreateHolderWallet,
} from "../../services/api";
import { parseOid4vpRequestSessionId } from "../../utils/oid4vpRequestUri";
import {
  ClipboardPaste,
  CheckCircle2,
} from "lucide-react";

export const ScanQrPage: React.FC = () => {
  const navigate = useNavigate();

  const [credentialOffer, setCredentialOffer] = useState<{
    preAuthorizedCode: string;
    configurationId: string;
    issuer?: string;
  } | null>(null);
  const [inputUri, setInputUri] = useState<string>("");
  const [offerConsent, setOfferConsent] = useState(false);
  const [claiming, setClaiming] = useState<boolean>(false);
  const [claimSuccess, setClaimSuccess] = useState<boolean>(false);
  const [claimedCredId, setClaimedCredId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProcessUri = async (uri: string) => {
    setError(null);
    setClaimSuccess(false);
    setCredentialOffer(null);
    setOfferConsent(false);

    const trimmed = uri.trim();
    if (!trimmed) {
      setError("Please paste a valid openid-credential-offer:// or openid4vp:// URI.");
      return;
    }

    // 1. OID4VCI Offer Flow: parse and review before requesting issuance.
    if (trimmed.startsWith("openid-credential-offer://")) {
      try {
        // Extract credential_offer param
        const url = new URL(trimmed.replace("openid-credential-offer://", "https://placeholder/"));
        const rawOffer = url.searchParams.get("credential_offer");
        if (!rawOffer) {
          throw new Error("This wallet supports inline credential_offer values; credential_offer_uri links are not supported.");
        }
        const parsed = JSON.parse(rawOffer) as {
          credential_issuer?: unknown;
          credential_configuration_ids?: unknown;
          grants?: Record<string, { "pre-authorized_code"?: unknown } | undefined>;
        };
        const preAuthCode = parsed.grants?.["urn:ietf:params:oauth:grant-type:pre-authorized_code"]?.["pre-authorized_code"];
        const configurationIds = parsed.credential_configuration_ids;
        if (typeof preAuthCode !== "string" || !preAuthCode) {
          throw new Error("Credential offer does not include a pre-authorized code.");
        }
        if (!Array.isArray(configurationIds) || configurationIds.length !== 1 || typeof configurationIds[0] !== "string") {
          throw new Error("This wallet can claim one credential configuration per offer.");
        }
        setCredentialOffer({
          preAuthorizedCode: preAuthCode,
          configurationId: configurationIds[0],
          issuer: typeof parsed.credential_issuer === "string" ? parsed.credential_issuer : undefined,
        });
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to claim OID4VCI offer.");
      }
      return;
    }

    // 2. OID4VP Presentation Flow
    if (trimmed.startsWith("openid4vp://")) {
      try {
        const sessionId = parseOid4vpRequestSessionId(trimmed);

        navigate("/wallet/consent", {
          state: {
            sessionId,
            requestUri: trimmed,
          },
        });
      } catch (err: unknown) {
        setError("Failed to parse OID4VP URI: " + (err instanceof Error ? err.message : String(err)));
      }
      return;
    }

    setError("Unrecognized QR protocol. Must start with openid-credential-offer:// or openid4vp://");
  };

  const handleAcceptCredentialOffer = async () => {
    if (!credentialOffer || !offerConsent || claiming) return;
    setClaiming(true);
    setError(null);
    try {
      const wallet = await getOrCreateHolderWallet();
      const res = await claimOid4vciOffer({
        preAuthorizedCode: credentialOffer.preAuthorizedCode,
        holderDid: wallet.holderDid,
        walletId: wallet.walletId,
        credentialConfigurationId: credentialOffer.configurationId,
      });
      setClaimedCredId(res.credentialId);
      setClaimSuccess(true);
      setCredentialOffer(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to claim OID4VCI offer.");
    } finally {
      setClaiming(false);
    }
  };

  return (
    <main className="holder-page holder-scan-page">
      <header className="holder-page-header">
        <div>
          <p className="holder-page-eyebrow">WALLET ACTION</p>
          <h1>Open an offer or request</h1>
          <p>Continue from a real OpenID credential offer or verifier request.</p>
        </div>
      </header>
      <section
        className="holder-scan-panel"
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: "200px",
            height: "200px",
            borderRadius: "20px",
            border: "1px solid #1f2937",
            backgroundColor: "#0d131f",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            marginBottom: "18px",
            boxShadow: "inset 0 0 20px rgba(37,99,235,0.08)",
          }}
        >
            <ClipboardPaste size={36} color="#60a5fa" style={{ marginBottom: "8px" }} aria-hidden="true" />
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            Paste a live wallet URI
          </span>
        </div>

        <div className="holder-scan-supported-flows" aria-label="Supported URI types">
          <span>Credential offer</span><span>Verifier request</span>
        </div>
        <p className="holder-scan-explanation">
          Paste the URI provided by the issuer or verifier. This web flow does not access your camera; the relevant service validates the request.
        </p>

        {error && (
          <div
            className="holder-inline-error"
            role="alert"
            id="holder-request-error"
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#f87171",
              fontSize: "0.8rem",
              marginBottom: "16px",
              textAlign: "left",
            }}
          >
            {error}
          </div>
        )}

        {claimSuccess && (
          <div
            className="holder-inline-success"
            role="status"
            style={{
              width: "100%",
              padding: "16px",
              borderRadius: "12px",
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#34d399",
              fontSize: "0.85rem",
              marginBottom: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              textAlign: "left",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700 }}>
              <CheckCircle2 size={18} />
              Credential received from the issuer
            </div>
            <div style={{ fontSize: "0.75rem", color: "#94a3b8", fontFamily: "var(--font-mono)" }}>
              ID: {claimedCredId}
            </div>
            <button
              type="button"
              onClick={() => navigate("/wallet")}
              style={{
                marginTop: "4px",
                padding: "8px 14px",
                borderRadius: "6px",
                backgroundColor: "#059669",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.8rem",
                border: "none",
                cursor: "pointer",
                width: "fit-content",
              }}
            >
              View in Wallet Vault →
            </button>
          </div>
        )}

        {credentialOffer && (
          <section className="holder-offer-review" aria-labelledby="holder-offer-review-title">
            <div>
              <p className="holder-page-eyebrow">OFFER REVIEW</p>
              <h2 id="holder-offer-review-title">Credential not received yet</h2>
              <p>Confirm only if you trust this issuer. The offer metadata does not include the issued credential claims, so they cannot be previewed here.</p>
            </div>
            <dl>
              <div><dt>Issuer</dt><dd>{credentialOffer.issuer || "Not supplied by offer"}</dd></div>
              <div><dt>Credential profile</dt><dd>{credentialOffer.configurationId}</dd></div>
            </dl>
            <label className="holder-offer-consent">
              <input type="checkbox" checked={offerConsent} onChange={(event) => setOfferConsent(event.target.checked)} />
              <span>I reviewed the available offer details and want the issuer to issue this credential to my wallet.</span>
            </label>
            <div className="holder-offer-review__actions">
              <button type="button" className="holder-secondary-action" onClick={() => { setCredentialOffer(null); setOfferConsent(false); }} disabled={claiming}>Close offer</button>
              <button type="button" className="holder-primary-action" onClick={handleAcceptCredentialOffer} disabled={claiming || !offerConsent}>
                {claiming ? "Contacting issuer…" : "Accept and request credential"}
              </button>
            </div>
          </section>
        )}

        {/* Manual URI Input */}
        <div className="holder-scan-form">
          <label htmlFor="holder-request-uri">Credential offer or verifier request URI</label>
          <input
            id="holder-request-uri"
            type="text"
            placeholder="openid-credential-offer://… or openid4vp://…"
            value={inputUri}
            onChange={(e) => setInputUri(e.target.value)}
            aria-invalid={!!error}
            aria-describedby={error ? "holder-request-error" : "holder-request-help"}
            autoComplete="off"
            spellCheck={false}
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: "#0d131f",
              border: "1px solid #1f2937",
              color: "#ffffff",
              fontSize: "0.8rem",
              fontFamily: "var(--font-mono)",
            }}
          />
          <button
            type="button"
            onClick={() => handleProcessUri(inputUri)}
            disabled={claiming || !inputUri.trim()}
            className="holder-primary-action"
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.85rem",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            Review URI
          </button>
        </div>

        {/* The URI must come from a live backend-issued request or offer. */}
        <div id="holder-request-help" className="holder-scan-help">
          <span>Supported schemes</span>
          <code>openid-credential-offer://</code>
          <code>openid4vp://</code>
        </div>
      </section>
    </main>
  );
};
