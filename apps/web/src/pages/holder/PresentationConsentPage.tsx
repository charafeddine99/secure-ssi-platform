import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  createWalletOid4vpPresentation,
  evaluateOid4vpSession,
  fetchCredentials,
  getOid4vpHolderRequest,
  getOrCreateHolderWallet,
  recordWalletOid4vpConsent,
  submitOid4vpDirectPost,
  Oid4vpHolderRequest,
  BackendCredential,
  HolderWallet,
} from "../../services/api";
import {
  CheckCircle2,
  ArrowLeft,
  Send,
  AlertCircle,
  XCircle,
  Clock,
  UserCheck,
  ShieldAlert,
} from "lucide-react";
import {
  getOid4vpSubmissionErrorMessage,
  Oid4vpSubmissionStage,
} from "../../utils/oid4vpSubmissionError";

export const PresentationConsentPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const stateSessionId: string = (() => {
    // A consent decision is bound to a verifier-created session.
    if (typeof location.state?.sessionId === "string" && location.state.sessionId) {
      return location.state.sessionId;
    }
    const params = new URLSearchParams(location.search);
    const queryId = params.get("sessionId");
    if (queryId) return queryId;
    return "";
  })();

  const [session, setSession] = useState<Oid4vpHolderRequest | null>(null);
  const [wallet, setWallet] = useState<HolderWallet | null>(null);
  const [matchedCredentials, setMatchedCredentials] = useState<BackendCredential[]>([]);
  const [selectedCredentialId, setSelectedCredentialId] = useState("");
  const [loadingRequest, setLoadingRequest] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string>("");
  const [explicitConsent, setExplicitConsent] = useState(false);
  const [presenting, setPresenting] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [pendingPresentation, setPendingPresentation] = useState<Parameters<typeof submitOid4vpDirectPost>[0] | null>(null);
  const [approvalBlocked, setApprovalBlocked] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "rejected" | "error"; text: string } | null>(null);

  const selectedCredential = matchedCredentials.find((credential) => credential.id === selectedCredentialId);
  const subject = selectedCredential?.raw_credential?.credentialSubject;
  const claimsData = subject && typeof subject === "object" && !Array.isArray(subject)
    ? Object.fromEntries(Object.entries(subject as Record<string, unknown>).filter(([key]) => key !== "id"))
    : {};
  const verifierName = session?.clientId || session?.verifierDid || "Unknown verifier";
  const purpose = session?.purpose || "No purpose supplied";

  // Load only an existing verifier session and credentials from the authenticated holder wallet.
  useEffect(() => {
    let active = true;
    const loadConsentContext = async () => {
      setLoadingRequest(true);
      setLoadError(null);
      if (!stateSessionId) {
        setLoadError("Open this page from an active verifier request. No request was supplied.");
        setLoadingRequest(false);
        return;
      }
      try {
        const data = await getOid4vpHolderRequest(stateSessionId);
        if (data.status !== "PENDING" || data.consentStatus && data.consentStatus !== "PENDING") {
          throw new Error(`This verification request is ${data.status.toLowerCase()} and cannot receive consent.`);
        }
        const holderWallet = await getOrCreateHolderWallet();
        const credentials = await fetchCredentials(undefined, undefined, holderWallet.walletId);
        const usableCredentials = credentials.filter((credential) => credential.status === "ACTIVE" && credential.raw_credential);
        if (usableCredentials.length === 0) {
          throw new Error("The authenticated holder wallet has no active credentials available for this request.");
        }
        const evaluation = await evaluateOid4vpSession(
          stateSessionId,
          usableCredentials.map((credential) => credential.raw_credential as Record<string, unknown>),
        );
        if (!evaluation.isSatisfied) {
          throw new Error(evaluation.unsatisfiedReason || "No wallet credential satisfies this verifier request.");
        }
        const queryIds = evaluation.details?.selectedQueryIds || [...new Set(evaluation.matchedCredentials.map((match) => match.queryId))];
        if (queryIds.length !== 1) {
          throw new Error("This consent screen supports one DCQL credential query at a time. The request was not approved.");
        }
        const matchedIds = new Set(
          evaluation.matchedCredentials
            .filter((match) => match.queryId === queryIds[0])
            .map((match) => match.credentialId),
        );
        const matches = usableCredentials.filter((credential) => matchedIds.has(credential.id));
        if (matches.length === 0) throw new Error("The request did not match an active credential in this wallet.");
        if (!active) return;
        setSession(data);
        setWallet(holderWallet);
        setMatchedCredentials(matches);
        setSelectedCredentialId(matches[0].id);
        setExpiresAt(data.expiresAt);
      } catch (err) {
        if (active) setLoadError(err instanceof Error ? err.message : "Could not load the verification request.");
      } finally {
        if (active) setLoadingRequest(false);
      }
    };

    void loadConsentContext();
    return () => { active = false; };
  }, [stateSessionId]);

  const handleApprove = async () => {
    if (!session || !wallet || !selectedCredential || !explicitConsent || Object.keys(claimsData).length === 0 || pendingPresentation || approvalBlocked) {
      setStatusMessage({ type: "error", text: "You must provide explicit consent before disclosing attributes." });
      return;
    }

    setPresenting(true);
    setStatusMessage(null);
    let stage: Oid4vpSubmissionStage = "consent";

    try {
      await recordWalletOid4vpConsent({
        sessionId: session.sessionId,
        walletId: wallet.walletId,
        holderDid: wallet.holderDid,
        action: "APPROVE",
        approvedCredentials: [selectedCredential.id],
        approvedClaims: claimsData,
      });
      stage = "presentation";
      const presentation = await createWalletOid4vpPresentation({
        sessionId: session.sessionId,
        walletId: wallet.walletId,
        credentialIds: [selectedCredential.id],
        disclosedClaims: claimsData,
      });
      const preparedPresentation: Parameters<typeof submitOid4vpDirectPost>[0] = {
        sessionId: session.sessionId,
        vpToken: presentation.vpToken,
        disclosedClaims: claimsData,
      };
      setPendingPresentation(preparedPresentation);
      stage = "direct-post";
      const response = await submitOid4vpDirectPost(preparedPresentation);
      setPendingPresentation(null);
      if (response.result.finalPolicyResult !== "ACCEPTED") {
        setStatusMessage({
          type: "rejected",
          text: `The verifier processed the presentation and returned ${response.result.finalPolicyResult || "an unknown policy result"}.`,
        });
      } else {
        setStatusMessage({ type: "success", text: "The verifier accepted the backend verification result." });
      }
    } catch (err: unknown) {
      if (stage !== "direct-post") {
        setPendingPresentation(null);
        setApprovalBlocked(true);
      }
      setStatusMessage({ type: "error", text: getOid4vpSubmissionErrorMessage(err, stage) });
    } finally {
      setPresenting(false);
    }
  };

  const handleRetryDirectPost = async () => {
    if (!pendingPresentation || presenting) return;

    setPresenting(true);
    setStatusMessage(null);
    try {
      const response = await submitOid4vpDirectPost(pendingPresentation);
      setPendingPresentation(null);
      if (response.result.finalPolicyResult !== "ACCEPTED") {
        setStatusMessage({
          type: "rejected",
          text: `The verifier processed the presentation and returned ${response.result.finalPolicyResult || "an unknown policy result"}.`,
        });
      } else {
        setStatusMessage({ type: "success", text: "The verifier accepted the backend verification result." });
      }
    } catch (err: unknown) {
      setStatusMessage({
        type: "error",
        text: getOid4vpSubmissionErrorMessage(err, "direct-post"),
      });
    } finally {
      setPresenting(false);
    }
  };

  const handleReject = async () => {
    if (!session || !wallet) {
      setStatusMessage({ type: "error", text: "A loaded request and authenticated holder wallet are required to reject." });
      return;
    }
    setRejecting(true);
    setStatusMessage(null);

    try {
      await recordWalletOid4vpConsent({
        sessionId: session.sessionId,
        walletId: wallet.walletId,
        holderDid: wallet.holderDid,
        action: "REJECT",
        rejectionReason: "Holder declined the verification request.",
      });
      setStatusMessage({ type: "rejected", text: "The holder-bound consent decision declined this request." });
    } catch (err: unknown) {
      setStatusMessage({ type: "error", text: err instanceof Error ? err.message : "Failed to reject verification session." });
    } finally {
      setRejecting(false);
    }
  };

  const revealedCount = Object.keys(claimsData).length;

  return (
    <main className="holder-page holder-consent-page">
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
          padding: 0,
        }}
      >
        <ArrowLeft size={16} />
        Back to Wallet Vault
      </button>

      <section
        className="holder-consent-panel"
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
        }}
      >
        <header className="holder-page-header holder-consent-header">
          <div>
          <p className="holder-page-eyebrow">CONSENT REVIEW</p>
          <h1>
            Review a verification request
          </h1>
          <p>
            Review the verifier request and choose a matching credential. This profile sends the complete signed credential; it does not provide claim-level cryptographic selective disclosure.
          </p>
          </div>
        </header>

        {loadingRequest && <p className="holder-inline-status" role="status">Loading the verifier request and authenticated wallet credentials…</p>}
        {loadError && (
          <div role="alert" style={{ padding: "12px 16px", borderRadius: "8px", backgroundColor: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#f87171", fontSize: "0.85rem" }}>
            {loadError}
          </div>
        )}

        {/* Status / Feedback Banner */}
        {statusMessage && (
          <div
            className={`holder-notice holder-notice--${statusMessage.type}`}
            data-status={statusMessage.type}
            role={statusMessage.type === "error" ? "alert" : "status"}
            style={{
              padding: "12px 16px",
              borderRadius: "8px",
              backgroundColor:
                statusMessage.type === "success"
                  ? "rgba(16, 185, 129, 0.15)"
                  : statusMessage.type === "rejected"
                  ? "rgba(245, 158, 11, 0.15)"
                  : "rgba(239, 68, 68, 0.15)",
              border: `1px solid ${
                statusMessage.type === "success"
                  ? "rgba(16, 185, 129, 0.3)"
                  : statusMessage.type === "rejected"
                  ? "rgba(245, 158, 11, 0.3)"
                  : "rgba(239, 68, 68, 0.3)"
              }`,
              color:
                statusMessage.type === "success"
                  ? "#34d399"
                  : statusMessage.type === "rejected"
                  ? "#fbbf24"
                  : "#f87171",
              fontSize: "0.85rem",
              display: "flex",
              alignItems: "flex-start",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            {statusMessage.type === "success" ? (
              <CheckCircle2 size={18} />
            ) : statusMessage.type === "rejected" ? (
              <ShieldAlert size={18} />
            ) : (
              <AlertCircle size={18} />
            )}
            <span style={{ flex: "1 1 220px", minWidth: 0, overflowWrap: "anywhere" }}>{statusMessage.text}</span>
            {statusMessage.type !== "error" && !pendingPresentation && (
              <button type="button" className="holder-secondary-action" onClick={() => navigate("/wallet")}>
                Return to wallet
              </button>
            )}
            {pendingPresentation && statusMessage.type === "error" && (
              <button
                type="button"
                onClick={handleRetryDirectPost}
                disabled={presenting}
                style={{
                  marginLeft: "auto",
                  flex: "0 1 220px",
                  maxWidth: "100%",
                  alignSelf: "flex-start",
                  padding: "8px 10px",
                  borderRadius: "8px",
                  border: "1px solid rgba(248, 113, 113, 0.45)",
                  backgroundColor: "rgba(127, 29, 29, 0.35)",
                  color: "#fecaca",
                  fontWeight: 700,
                  cursor: presenting ? "not-allowed" : "pointer",
                }}
              >
                {presenting ? "Retrying delivery…" : "Retry sending the same presentation"}
              </button>
            )}
          </div>
        )}

        {/* Verifier Purpose & Retention Box */}
        <section
          className="holder-consent-request-card"
          style={{
            backgroundColor: "#0d131f",
            borderRadius: "12px",
            border: "1px solid #1f2937",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>
              Requesting Authority (Verifier)
            </span>
            <span style={{ fontSize: "0.75rem", color: "#38bdf8", fontFamily: "var(--font-mono)" }}>
              {session ? `Session: ${session.sessionId.substring(0, 18)}…` : "No active request"}
            </span>
          </div>
          <div style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", display: "flex", alignItems: "center", gap: "6px" }}>
            <UserCheck size={18} color="#60a5fa" />
            {verifierName}
          </div>
          <div style={{ fontSize: "0.82rem", color: "#cbd5e1", backgroundColor: "rgba(30, 41, 59, 0.5)", padding: "10px", borderRadius: "8px" }}>
            <strong style={{ color: "#93c5fd" }}>Purpose of Request:</strong> {purpose}
          </div>
          {expiresAt && (
            <div style={{ fontSize: "0.75rem", color: "#94a3b8", display: "flex", alignItems: "center", gap: "4px" }}>
              <Clock size={14} />
              Session Valid Until: {new Date(expiresAt).toLocaleTimeString()}
            </div>
          )}
        </section>

        {matchedCredentials.length > 1 && (
          <fieldset className="holder-consent-credential-picker" disabled={loadingRequest || presenting || rejecting} style={{ border: "1px solid #334155", borderRadius: "10px", padding: "14px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <legend style={{ color: "#f8fafc", fontSize: "0.85rem", fontWeight: 700, padding: "0 6px" }}>Choose one matching credential</legend>
            {matchedCredentials.map((credential) => (
              <label key={credential.id} style={{ display: "flex", gap: "10px", alignItems: "flex-start", padding: "10px", borderRadius: "8px", backgroundColor: selectedCredentialId === credential.id ? "rgba(37, 99, 235, 0.12)" : "#0d131f", cursor: "pointer" }}>
                <input type="radio" name="credential" value={credential.id} checked={selectedCredentialId === credential.id} onChange={() => { setSelectedCredentialId(credential.id); setExplicitConsent(false); }} />
                <span style={{ color: "#e2e8f0", fontSize: "0.82rem" }}>
                  <strong>{credential.title || credential.credential_type}</strong><br />
                  {credential.issuer_name || credential.issuer} · {credential.status}
                </span>
              </label>
            ))}
          </fieldset>
        )}

        {/* Complete credential disclosure summary */}
        <div
          className="holder-consent-disclosure-summary"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "10px 14px",
            borderRadius: "8px",
            backgroundColor: "rgba(37, 99, 235, 0.1)",
            border: "1px solid rgba(37, 99, 235, 0.25)",
            fontSize: "0.8rem",
          }}
        >
          <span style={{ color: "#93c5fd" }}><strong>{revealedCount}</strong> credential claims</span>
          <span style={{ color: "#fbbf24", fontWeight: 600 }}>The complete signed credential will be included</span>
        </div>

        {/* Read-only claim inventory: this proof suite cannot omit individual signed claims. */}
        <section className="holder-consent-claims" aria-labelledby="holder-consent-claims-title">
          <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#f8fafc" }}>
            <span id="holder-consent-claims-title">Claims in the selected credential</span>
          </span>

          {Object.entries(claimsData).map(([key, val]) => {
            return (
              <div key={key} className="holder-consent-claim" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 14px", borderRadius: "10px", backgroundColor: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(59, 130, 246, 0.4)" }}>
                <div>
                  <div style={{ fontSize: "0.84rem", fontWeight: 600, color: "#f8fafc" }}>{key}</div>
                  <div style={{ fontSize: "0.75rem", color: "#93c5fd", marginTop: "2px" }}>{String(val)}</div>
                </div>
                <span style={{ fontSize: "0.72rem", padding: "2px 8px", borderRadius: "4px", fontWeight: 600, backgroundColor: "rgba(245, 158, 11, 0.15)", color: "#fbbf24" }}>INCLUDED</span>
              </div>
            );
          })}
          {revealedCount === 0 && !loadingRequest && <p style={{ color: "#f87171", fontSize: "0.82rem" }}>No credential is selected. Sharing is unavailable.</p>}
        </section>

        {/* Explicit Consent Checkbox */}
        <label
          className="holder-consent-checkbox"
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "10px",
            padding: "12px",
            borderRadius: "8px",
            backgroundColor: "rgba(30, 41, 59, 0.4)",
            border: "1px solid #1f2937",
            cursor: "pointer",
            fontSize: "0.8rem",
            color: "#e2e8f0",
            lineHeight: 1.4,
          }}
        >
          <input
            type="checkbox"
            checked={explicitConsent}
            onChange={(e) => setExplicitConsent(e.target.checked)}
            aria-label="Explicit holder consent to disclose complete selected credential"
            style={{ marginTop: "2px", accentColor: "#2563eb", cursor: "pointer" }}
          />
          <span>
            I explicitly consent to send the complete selected credential, including all <strong>{revealedCount} claims</strong>, to <strong>{verifierName}</strong> for the stated purpose.
          </span>
        </label>

        {/* Action Buttons: Approve vs Reject */}
        <div className="holder-consent-actions" style={{ display: "flex", flexWrap: "wrap", gap: "12px", marginTop: "6px" }}>
          <button
            type="button"
            className="holder-danger-action"
            onClick={handleReject}
            disabled={loadingRequest || !!loadError || !session || !wallet || rejecting || presenting || approvalBlocked || !!pendingPresentation}
            style={{
              flex: "1 1 140px",
              minWidth: 0,
              padding: "12px",
              borderRadius: "10px",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#f87171",
              fontWeight: 700,
              fontSize: "0.9rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
            }}
          >
            <XCircle size={16} />
            {rejecting ? "Rejecting..." : "Reject Request"}
          </button>

          <button
            type="button"
            className="holder-primary-action"
            onClick={handleApprove}
            disabled={loadingRequest || !!loadError || !session || !wallet || !selectedCredential || presenting || rejecting || !explicitConsent || approvalBlocked || !!pendingPresentation}
            style={{
              flex: "2 1 220px",
              minWidth: 0,
              padding: "12px",
              borderRadius: "10px",
              backgroundColor: presenting ? "#1d4ed8" : "#2563eb",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.9rem",
              border: "none",
              cursor: loadingRequest || !!loadError || !selectedCredential || presenting || !explicitConsent || approvalBlocked || !!pendingPresentation ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              opacity: explicitConsent ? 1 : 0.6,
            }}
          >
            <Send size={16} />
            {presenting ? "Creating and verifying presentation…" : pendingPresentation ? "Presentation prepared; delivery is pending" : `Share complete credential (${revealedCount} claims)`}
          </button>
        </div>
      </section>
    </main>
  );
};
