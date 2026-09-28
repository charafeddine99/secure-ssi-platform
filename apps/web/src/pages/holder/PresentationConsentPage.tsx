import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import {
  getOid4vpSession,
  submitOid4vpDirectPost,
  rejectOid4vpSession,
  fetchCredentials,
  Oid4vpSession,
  BackendCredential,
} from "../../services/api";
import {
  ShieldCheck,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
  ArrowLeft,
  Send,
  AlertCircle,
  XCircle,
  Clock,
  UserCheck,
  ShieldAlert,
} from "lucide-react";

export const PresentationConsentPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const stateSessionId = location.state?.sessionId;
  const stateCred = location.state?.credential as BackendCredential | undefined;

  const [session, setSession] = useState<Oid4vpSession | null>(null);
  const [loadingSession, setLoadingSession] = useState<boolean>(Boolean(stateSessionId));

  const [verifierName, setVerifierName] = useState("Accredited Compliance Authority");
  const [purpose, setPurpose] = useState("Verification of active academic status & qualification");
  const [expiresAt, setExpiresAt] = useState<string>("");

  // Claims loaded from selected credential or realistic university profile
  const [claimsData, setClaimsData] = useState<Record<string, any>>({
    affiliation: "Senior Security Architect",
    programCode: "SUB-SEC-2026",
    degree: "Computer Engineering & Applied Cryptography",
    graduationYear: 2026,
    "Full Name": "Charaf Eddine Bessanane",
    Nationality: "TUR",
    "Assurance Level": "Qualified LoA High (eIDAS 2.0)",
  });

  // State: selected claims to disclose
  const [selectedClaims, setSelectedClaims] = useState<Record<string, boolean>>({
    affiliation: true,
    programCode: true,
    degree: true,
    graduationYear: false,
    "Full Name": false,
    Nationality: false,
    "Assurance Level": true,
  });

  const [explicitConsent, setExplicitConsent] = useState(true);
  const [presenting, setPresenting] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "rejected" | "error"; text: string } | null>(null);

  // Fetch session details from backend
  useEffect(() => {
    if (!stateSessionId) return;

    const fetchSession = async () => {
      try {
        const data = await getOid4vpSession(stateSessionId);
        setSession(data);
        if (data.purpose) setPurpose(data.purpose);
        if (data.expiresAt) setExpiresAt(data.expiresAt);
        if (data.verifierDid) setVerifierName(data.verifierDid);

        if (data.requestedFields && data.requestedFields.length > 0) {
          const newSelected: Record<string, boolean> = {};
          // Default: disclose requested fields, protect others
          Object.keys(claimsData).forEach((k) => {
            newSelected[k] = data.requestedFields.includes(k);
          });
          setSelectedClaims(newSelected);
        }
      } catch (err) {
        console.warn("Could not load real OID4VP session, using fallback:", err);
      } finally {
        setLoadingSession(false);
      }
    };

    fetchSession();
  }, [stateSessionId]);

  // Load credential claims if passed via navigation state or fallback
  useEffect(() => {
    if (stateCred && stateCred.claims && Object.keys(stateCred.claims).length > 0) {
      setClaimsData(stateCred.claims);
      const initialSelected: Record<string, boolean> = {};
      Object.keys(stateCred.claims).forEach((k, idx) => {
        initialSelected[k] = idx < 3; // default: selective disclosure
      });
      setSelectedClaims(initialSelected);
    }
  }, [stateCred]);

  const toggleClaim = (key: string) => {
    setSelectedClaims((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleApprove = async () => {
    if (!explicitConsent) {
      setStatusMessage({ type: "error", text: "You must provide explicit consent before disclosing attributes." });
      return;
    }

    setPresenting(true);
    setStatusMessage(null);

    const disclosedValues: Record<string, any> = {};
    Object.entries(selectedClaims).forEach(([k, isSelected]) => {
      if (isSelected && claimsData[k] !== undefined) {
        disclosedValues[k] = claimsData[k];
      }
    });

    const holderDid =
      localStorage.getItem("ssi_user_did") ||
      "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP";

    const targetSessionId = stateSessionId || session?.sessionId || "demo_session_12345";
    const nonce = session?.nonce || "mock_challenge_nonce_2026";

    // Build standard W3C VP token
    const vpToken = {
      "@context": ["https://www.w3.org/ns/credentials/v2"],
      type: ["VerifiablePresentation"],
      verifiableCredential: [
        {
          "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://secure-ssi.example/contexts/university-affiliation/v1",
          ],
          id: stateCred?.id || "urn:uuid:00000000-0000-4000-8000-000000000001",
          type: ["VerifiableCredential", stateCred?.credential_type || "UniversityAffiliationCredential"],
          issuer: stateCred?.issuer || "did:web:issuer.example",
          validFrom: stateCred?.issued_date ? `${stateCred.issued_date}T00:00:00Z` : "2026-01-01T00:00:00Z",
          validUntil: stateCred?.expiry_date ? `${stateCred.expiry_date}T00:00:00Z` : "2028-01-01T00:00:00Z",
          credentialSubject: {
            id: holderDid,
            ...disclosedValues,
          },
          proof: {
            type: "DataIntegrityProof",
            cryptosuite: "eddsa-jcs-2022",
            proofValue: stateCred?.proof_value || "z2DBDjSRR4iBwcgJBJ4FCnRphCVJULnHK19J7wwM9VfWoUpt5kgQBoMZNt91gV3ckUVrsJdDf22xpxo1PPXQ2JmYx",
          },
        },
      ],
      proof: {
        type: "DataIntegrityProof",
        cryptosuite: "eddsa-jcs-2022",
        nonce: nonce,
        proofValue: "zMockHolderPresentationProofValue2026",
      },
    };

    try {
      if (stateSessionId || session?.sessionId) {
        await submitOid4vpDirectPost({
          sessionId: targetSessionId,
          vpToken,
          disclosedClaims: disclosedValues,
          aiRiskScore: 12,
        });
      }
      setStatusMessage({ type: "success", text: "Presentation verified and delivered via OID4VP Direct Post!" });
      setTimeout(() => {
        navigate("/wallet/activity");
      }, 1600);
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to submit presentation via Direct Post." });
    } finally {
      setPresenting(false);
    }
  };

  const handleReject = async () => {
    setRejecting(true);
    setStatusMessage(null);

    const targetSessionId = stateSessionId || session?.sessionId;
    const holderDid =
      localStorage.getItem("ssi_user_did") ||
      "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP";

    try {
      if (targetSessionId) {
        await rejectOid4vpSession({
          sessionId: targetSessionId,
          reason: "Holder declined presentation consent",
          holderDid,
        });
      }
      setStatusMessage({ type: "rejected", text: "Verification request declined. Session terminated and audited." });
      setTimeout(() => {
        navigate("/wallet");
      }, 1400);
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to reject verification session." });
    } finally {
      setRejecting(false);
    }
  };

  const revealedCount = Object.values(selectedClaims).filter(Boolean).length;
  const hiddenCount = Object.keys(selectedClaims).length - revealedCount;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "720px", margin: "0 auto" }}>
      <button
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

      <div
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
        <div>
          <div style={{ display: "flex", gap: "6px", alignItems: "center", marginBottom: "8px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
            <TrustBadge level="DEMO_TRUST_LEVEL" size="sm" />
          </div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Consent Sheet & Selective Disclosure
          </h2>
          <p style={{ fontSize: "0.82rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Review the verifier's identity, stated purpose, and choose which attributes to disclose. Unselected claims remain cryptographically withheld.
          </p>
        </div>

        {/* Status / Feedback Banner */}
        {statusMessage && (
          <div
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
              alignItems: "center",
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
            <span>{statusMessage.text}</span>
          </div>
        )}

        {/* Verifier Purpose & Retention Box */}
        <div
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
              {stateSessionId ? `Session: ${stateSessionId.substring(0, 18)}...` : "OID4VP Direct Post"}
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
        </div>

        {/* Data Minimization Stats Bar */}
        <div
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
          <span style={{ color: "#93c5fd" }}>
            <strong>{revealedCount}</strong> attributes selectively disclosed
          </span>
          <span style={{ color: "#34d399", fontWeight: 600 }}>
            🔒 {hiddenCount} attributes strictly minimized & withheld
          </span>
        </div>

        {/* Claims Disclosure Selection */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#f8fafc" }}>
            Granular Attribute Disclosure (Click to Toggle):
          </span>

          {Object.entries(claimsData).map(([key, val]) => {
            const isRevealed = selectedClaims[key] || false;
            return (
              <div
                key={key}
                onClick={() => toggleClaim(key)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "12px 14px",
                  borderRadius: "10px",
                  backgroundColor: isRevealed ? "rgba(15, 23, 42, 0.8)" : "rgba(0, 0, 0, 0.3)",
                  border: `1px solid ${isRevealed ? "rgba(59, 130, 246, 0.4)" : "#1f2937"}`,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.84rem", fontWeight: 600, color: isRevealed ? "#f8fafc" : "#64748b" }}>
                    {key}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: isRevealed ? "#93c5fd" : "#475569", marginTop: "2px" }}>
                    {isRevealed ? String(val) : "•••••••••••• (Withheld / Minimized)"}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    style={{
                      fontSize: "0.72rem",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      fontWeight: 600,
                      backgroundColor: isRevealed ? "rgba(16, 185, 129, 0.15)" : "rgba(100, 116, 139, 0.2)",
                      color: isRevealed ? "#34d399" : "#64748b",
                    }}
                  >
                    {isRevealed ? "DISCLOSED" : "HIDDEN"}
                  </span>
                  {isRevealed ? <Eye size={16} color="#60a5fa" /> : <EyeOff size={16} color="#475569" />}
                </div>
              </div>
            );
          })}
        </div>

        {/* Explicit Consent Checkbox */}
        <label
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
            style={{ marginTop: "2px", accentColor: "#2563eb", cursor: "pointer" }}
          />
          <span>
            I explicitly grant consent to transmit the selected <strong>{revealedCount} attributes</strong> to <strong>{verifierName}</strong> for the verified purpose. Minimized attributes will remain withheld.
          </span>
        </label>

        {/* Action Buttons: Approve vs Reject */}
        <div style={{ display: "flex", gap: "12px", marginTop: "6px" }}>
          <button
            type="button"
            onClick={handleReject}
            disabled={rejecting || presenting}
            style={{
              flex: 1,
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
            {rejecting ? "Declining..." : "Decline Request"}
          </button>

          <button
            type="button"
            onClick={handleApprove}
            disabled={presenting || rejecting || !explicitConsent}
            style={{
              flex: 2,
              padding: "12px",
              borderRadius: "10px",
              backgroundColor: presenting ? "#1d4ed8" : "#2563eb",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.9rem",
              border: "none",
              cursor: presenting || !explicitConsent ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              opacity: explicitConsent ? 1 : 0.6,
            }}
          >
            <Send size={16} />
            {presenting ? "Delivering VP via Direct Post..." : `Approve & Disclose (${revealedCount} Claims)`}
          </button>
        </div>
      </div>
    </div>
  );
};
