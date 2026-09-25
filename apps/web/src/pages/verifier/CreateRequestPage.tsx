import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { QRCodeDisplay } from "../../components/common/QRCodeDisplay";
import { NinePointVerificationMatrix } from "../../components/verification/NinePointVerificationMatrix";
import {
  createOid4vpSession,
  getOid4vpSession,
  Oid4vpSession,
} from "../../services/api";
import {
  PlusCircle,
  QrCode,
  ArrowLeft,
  CheckCircle2,
  Copy,
  Check,
  ShieldCheck,
  Clock,
  Sparkles,
  Layers,
  RefreshCw,
} from "lucide-react";

export const CreateRequestPage: React.FC = () => {
  const navigate = useNavigate();

  const [purpose, setPurpose] = useState("Age verification and citizenship confirmation");
  const [credentialType, setCredentialType] = useState("UniversityAffiliationCredential");
  const [predicate, setPredicate] = useState("age >= 18");
  const [claims, setClaims] = useState(["affiliation", "degree", "programCode"]);
  const [ttlSeconds, setTtlSeconds] = useState(600);

  const [creatingSession, setCreatingSession] = useState(false);
  const [session, setSession] = useState<Oid4vpSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  const availableClaims = [
    "affiliation",
    "programCode",
    "degree",
    "graduationYear",
    "Full Name",
    "Nationality",
    "National ID No",
  ];

  const toggleClaim = (c: string) => {
    if (claims.includes(c)) setClaims(claims.filter((item) => item !== c));
    else setClaims([...claims, c]);
  };

  // Poll active session for status changes
  useEffect(() => {
    if (!session || session.status === "VERIFIED" || session.status === "REJECTED") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await getOid4vpSession(session.sessionId);
        if (updated.status !== session.status) {
          setSession(updated);
        }
      } catch (err) {
        // Silently retry polling
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [session]);

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingSession(true);
    setError(null);

    try {
      const newSession = await createOid4vpSession({
        purpose,
        requestedCredentialTypes: [credentialType],
        requestedFields: claims,
        ttlSeconds,
      });
      setSession(newSession);
    } catch (err: any) {
      setError(err.message || "Failed to create OID4VP verification session.");
    } finally {
      setCreatingSession(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "880px" }}>
      <button
        onClick={() => navigate("/verifier")}
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
        Back to Verifier Portal
      </button>

      <div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Create OID4VP Presentation Request
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Generate standards-compliant DIF Presentation Definition requests with real-time QR flow and 9-point verification.
        </p>
      </div>

      {error && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "8px",
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#f87171",
            fontSize: "0.85rem",
          }}
        >
          {error}
        </div>
      )}

      {session ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Active Session Card */}
          <div
            style={{
              backgroundColor: "#111827",
              borderRadius: "16px",
              border: "1px solid #1f2937",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div
                  style={{
                    padding: "8px",
                    borderRadius: "10px",
                    backgroundColor:
                      session.status === "VERIFIED"
                        ? "rgba(16, 185, 129, 0.2)"
                        : "rgba(59, 130, 246, 0.2)",
                    color: session.status === "VERIFIED" ? "#34d399" : "#60a5fa",
                  }}
                >
                  {session.status === "VERIFIED" ? <CheckCircle2 size={24} /> : <QrCode size={24} />}
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 700, color: "#ffffff" }}>
                    {session.status === "VERIFIED"
                      ? "Verifiable Presentation Verified!"
                      : "OID4VP Verification Session Active"}
                  </h3>
                  <p style={{ margin: "2px 0 0 0", fontSize: "0.8rem", color: "#94a3b8" }}>
                    {session.status === "VERIFIED"
                      ? "Direct Post presentation accepted and evaluated through 9-point security checklist."
                      : "Scan QR code with Holder Wallet to submit Verifiable Presentation via Direct Post."}
                  </p>
                </div>
              </div>

              {/* Status Badge */}
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 14px",
                  borderRadius: "9999px",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  backgroundColor:
                    session.status === "VERIFIED"
                      ? "rgba(16, 185, 129, 0.2)"
                      : "rgba(59, 130, 246, 0.2)",
                  color: session.status === "VERIFIED" ? "#34d399" : "#60a5fa",
                  border: `1px solid ${session.status === "VERIFIED" ? "rgba(16, 185, 129, 0.4)" : "rgba(59, 130, 246, 0.4)"}`,
                }}
              >
                {session.status === "PENDING" && <RefreshCw size={12} className="animate-spin" />}
                STATUS: {session.status}
              </div>
            </div>

            {/* If still PENDING: Show QR Code & Live Polling Instructions */}
            {session.status === "PENDING" && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  gap: "24px",
                  alignItems: "center",
                  backgroundColor: "#0d131f",
                  padding: "20px",
                  borderRadius: "12px",
                  border: "1px solid #1f2937",
                }}
              >
                <QRCodeDisplay
                  value={session.deepLinkUri}
                  size={210}
                  title="OID4VP QR Code"
                  subtitle="Draft 20 / Direct Post"
                />

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Session Identifier:</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#60a5fa" }}>
                      {session.sessionId}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Session Challenge Nonce:</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#38bdf8" }}>
                      {session.nonce}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Verification Purpose:</div>
                    <div style={{ fontSize: "0.85rem", color: "#ffffff", fontWeight: 500 }}>
                      {session.purpose}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Requested Fields:</div>
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "4px" }}>
                      {session.requestedFields.map((f) => (
                        <span
                          key={f}
                          style={{
                            padding: "3px 8px",
                            backgroundColor: "rgba(59, 130, 246, 0.15)",
                            color: "#93c5fd",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                          }}
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}>
                    <Clock size={14} color="#94a3b8" />
                    <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                      Polling backend every 2s for direct-post submission...
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* If VERIFIED: Show NinePointVerificationMatrix */}
            {session.status === "VERIFIED" && session.verificationResult && (
              <NinePointVerificationMatrix
                result={session.verificationResult}
                disclosedClaims={session.disclosedClaims}
                aiRiskScore={session.aiRiskScore || 12}
                nonce={session.nonce}
                sessionId={session.sessionId}
              />
            )}

            {/* Actions */}
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setSession(null)}
                style={{
                  padding: "10px 18px",
                  borderRadius: "8px",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Create Another Request
              </button>

              <button
                type="button"
                onClick={() => navigate("/verifier")}
                style={{
                  padding: "10px 18px",
                  borderRadius: "8px",
                  backgroundColor: "#1f2937",
                  color: "#e2e8f0",
                  border: "1px solid #374151",
                  fontSize: "0.85rem",
                  cursor: "pointer",
                }}
              >
                Back to Verifier Portal
              </button>
            </div>
          </div>
        </div>
      ) : (
        <form
          onSubmit={handleCreateSession}
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
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#60a5fa" }}>
            <Sparkles size={20} />
            <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>
              Configure OID4VP Presentation Session
            </h3>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
              Verification Purpose
            </label>
            <input
              type="text"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              style={{
                width: "100%",
                padding: "10px",
                borderRadius: "8px",
                backgroundColor: "#0d131f",
                border: "1px solid #1f2937",
                color: "#ffffff",
                fontSize: "0.85rem",
              }}
              required
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Target Credential Schema
              </label>
              <select
                value={credentialType}
                onChange={(e) => setCredentialType(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "8px",
                  backgroundColor: "#0d131f",
                  border: "1px solid #1f2937",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                }}
              >
                <option value="UniversityAffiliationCredential">
                  Higher Education Affiliation (W3C Profile)
                </option>
                <option value="QualifiedElectronicAttestationCredential">
                  Qualified Electronic Attestation (QEAA)
                </option>
                <option value="NationalIdentityCredential">
                  National Identity Attestation
                </option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Session Lifetime (TTL)
              </label>
              <select
                value={ttlSeconds}
                onChange={(e) => setTtlSeconds(Number(e.target.value))}
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "8px",
                  backgroundColor: "#0d131f",
                  border: "1px solid #1f2937",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                }}
              >
                <option value={300}>5 Minutes (300s)</option>
                <option value={600}>10 Minutes (600s)</option>
                <option value={1800}>30 Minutes (1800s)</option>
              </select>
            </div>
          </div>

          {/* Requested Claims Selector */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "6px" }}>
              Requested Claims (Selective Disclosure Policy)
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              {availableClaims.map((c) => {
                const selected = claims.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleClaim(c)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      border: `1px solid ${selected ? "#2563eb" : "#374151"}`,
                      backgroundColor: selected ? "rgba(37, 99, 235, 0.2)" : "#0d131f",
                      color: selected ? "#60a5fa" : "#94a3b8",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {selected ? "✓ " : "+ "}
                    {c}
                  </button>
                );
              })}
            </div>
          </div>

          <button
            type="submit"
            disabled={creatingSession}
            style={{
              width: "100%",
              padding: "12px",
              borderRadius: "10px",
              backgroundColor: "#059669",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.95rem",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              marginTop: "8px",
            }}
          >
            {creatingSession ? (
              <span>Generating OID4VP Session & Challenge Nonce...</span>
            ) : (
              <>
                <QrCode size={18} />
                Generate OID4VP Request & Live QR
              </>
            )}
          </button>
        </form>
      )}
    </div>
  );
};
