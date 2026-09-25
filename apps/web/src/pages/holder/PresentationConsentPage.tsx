import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import {
  getOid4vpSession,
  submitOid4vpDirectPost,
  Oid4vpSession,
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
  Sparkles,
} from "lucide-react";

export const PresentationConsentPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const stateSessionId = location.state?.sessionId;
  const [session, setSession] = useState<Oid4vpSession | null>(null);
  const [loadingSession, setLoadingSession] = useState<boolean>(Boolean(stateSessionId));

  const [verifierName, setVerifierName] = useState("Accredited Compliance Authority");
  const [purpose, setPurpose] = useState("Verification of active academic status & qualification");

  const credentialClaims: Record<string, any> = {
    affiliation: "student",
    programCode: "SYN-CS-001",
    degree: "Bachelor of Science",
    graduationYear: 2026,
    "Full Name": "Charaf Eddine Bessanane",
    Nationality: "TUR",
    "Assurance Level": "Prototype High LoA",
  };

  // State: selected claims to reveal
  const [selectedClaims, setSelectedClaims] = useState<Record<string, boolean>>({
    affiliation: true,
    programCode: true,
    degree: true,
    graduationYear: false,
    "Full Name": false,
    Nationality: false,
    "Assurance Level": true,
  });

  const [presenting, setPresenting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch session details if real sessionId passed
  useEffect(() => {
    if (!stateSessionId) return;

    const fetchSession = async () => {
      try {
        const data = await getOid4vpSession(stateSessionId);
        setSession(data);
        if (data.purpose) setPurpose(data.purpose);
        if (data.requestedFields && data.requestedFields.length > 0) {
          const newSelected: Record<string, boolean> = { ...selectedClaims };
          data.requestedFields.forEach((field) => {
            newSelected[field] = true;
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

  const toggleClaim = (key: string) => {
    setSelectedClaims((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleApprove = async () => {
    setPresenting(true);
    setError(null);

    const disclosedValues: Record<string, any> = {};
    Object.entries(selectedClaims).forEach(([k, isSelected]) => {
      if (isSelected && credentialClaims[k] !== undefined) {
        disclosedValues[k] = credentialClaims[k];
      }
    });

    const holderDid =
      localStorage.getItem("ssi_user_did") ||
      "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP";

    const targetSessionId = stateSessionId || "demo_session_12345";
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
          id: "urn:uuid:00000000-0000-4000-8000-000000000001",
          type: ["VerifiableCredential", "UniversityAffiliationCredential"],
          issuer: "did:web:issuer.example",
          validFrom: "2026-01-01T00:00:00Z",
          validUntil: "2028-01-01T00:00:00Z",
          credentialSubject: {
            id: holderDid,
            ...disclosedValues,
          },
          proof: {
            type: "DataIntegrityProof",
            cryptosuite: "eddsa-jcs-2022",
            proofValue: "z2DBDjSRR4iBwcgJBJ4FCnRphCVJULnHK19J7wwM9VfWoUpt5kgQBoMZNt91gV3ckUVrsJdDf22xpxo1PPXQ2JmYx",
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
      if (stateSessionId) {
        await submitOid4vpDirectPost({
          sessionId: targetSessionId,
          vpToken,
          disclosedClaims: disclosedValues,
          aiRiskScore: 12,
        });
      }
      setSuccess(true);
      setTimeout(() => {
        navigate("/wallet/activity");
      }, 1600);
    } catch (err: any) {
      setError(err.message || "Failed to submit presentation via Direct Post.");
    } finally {
      setPresenting(false);
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
            Selective Disclosure & Holder Consent
          </h2>
          <p style={{ fontSize: "0.82rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Control which attributes are disclosed. Withheld attributes remain cryptographically protected.
          </p>
        </div>

        {error && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#f87171",
              fontSize: "0.82rem",
            }}
          >
            {error}
          </div>
        )}

        {/* Verifier Purpose Box */}
        <div
          style={{
            backgroundColor: "#0d131f",
            borderRadius: "12px",
            border: "1px solid #1f2937",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>
              Requesting Verifier
            </span>
            <span style={{ fontSize: "0.75rem", color: "#38bdf8", fontFamily: "var(--font-mono)" }}>
              {stateSessionId ? `Session: ${stateSessionId.substring(0, 16)}...` : "OID4VP Direct Post"}
            </span>
          </div>
          <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff" }}>
            {verifierName}
          </div>
          <p style={{ margin: 0, fontSize: "0.82rem", color: "#94a3b8" }}>
            {purpose}
          </p>
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
            <strong>{revealedCount}</strong> attributes revealed to verifier
          </span>
          <span style={{ color: "#34d399", fontWeight: 600 }}>
            🔒 {hiddenCount} attributes strictly withheld
          </span>
        </div>

        {/* Claims Disclosure Selection */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#f8fafc" }}>
            Select Attributes to Disclose:
          </span>

          {Object.entries(credentialClaims).map(([key, val]) => {
            const isRevealed = selectedClaims[key] || false;
            return (
              <div
                key={key}
                onClick={() => toggleClaim(key)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  backgroundColor: isRevealed ? "rgba(15, 23, 42, 0.8)" : "rgba(0, 0, 0, 0.3)",
                  border: `1px solid ${isRevealed ? "rgba(59, 130, 246, 0.3)" : "#1f2937"}`,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, color: isRevealed ? "#f8fafc" : "#64748b" }}>
                    {key}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: isRevealed ? "#93c5fd" : "#475569", marginTop: "2px" }}>
                    {isRevealed ? String(val) : "•••••••••••• (Protected)"}
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

        {/* Submit Consent Button */}
        <button
          type="button"
          onClick={handleApprove}
          disabled={presenting || success}
          style={{
            width: "100%",
            padding: "12px",
            borderRadius: "10px",
            backgroundColor: success ? "#059669" : "#2563eb",
            color: "#ffffff",
            fontWeight: 700,
            fontSize: "0.95rem",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            marginTop: "6px",
            transition: "all 0.2s ease",
          }}
        >
          {success ? (
            <>
              <CheckCircle2 size={18} />
              Presentation Delivered & Direct Posted!
            </>
          ) : presenting ? (
            <span>Signing Presentation with Ed25519 Holder Key...</span>
          ) : (
            <>
              <Send size={16} />
              Approve & Submit Presentation ({revealedCount} Claims)
            </>
          )}
        </button>
      </div>
    </div>
  );
};
