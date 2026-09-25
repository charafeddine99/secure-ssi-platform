import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { RiskScorePanel } from "../../components/security/RiskScorePanel";
import { QRCodeDisplay } from "../../components/common/QRCodeDisplay";
import {
  issueCredential,
  assessFraudRisk,
  createOid4vciOffer,
  getOid4vciOffer,
  Oid4vciOffer,
} from "../../services/api";
import {
  PlusCircle,
  ShieldCheck,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Send,
  QrCode,
  Layers,
  Sparkles,
  KeyRound,
  Clock,
} from "lucide-react";

export const IssueCredentialPage: React.FC = () => {
  const navigate = useNavigate();

  // Mode: OID4VCI (Standard QR Flow) vs Direct Issuance
  const [activeTab, setActiveTab] = useState<"OID4VCI" | "DIRECT">("OID4VCI");

  // OID4VCI State
  const [oidConfigId, setOidConfigId] = useState<string>("UniversityAffiliationCredential");
  const [oidAffiliation, setOidAffiliation] = useState<string>("student");
  const [oidProgramCode, setOidProgramCode] = useState<string>("SYN-CS-001");
  const [oidDegree, setOidDegree] = useState<string>("Bachelor of Science");
  const [oidGradYear, setOidGradYear] = useState<number>(2026);
  const [oidTtlSeconds, setOidTtlSeconds] = useState<number>(1800);
  const [oidUserPin, setOidUserPin] = useState<string>("");
  const [generatingOffer, setGeneratingOffer] = useState<boolean>(false);
  const [oidOffer, setOidOffer] = useState<Oid4vciOffer | null>(null);
  const [offerClaimed, setOfferClaimed] = useState<boolean>(false);

  // Direct Push State
  const [category, setCategory] = useState<string>("IDENTITY");
  const [title, setTitle] = useState("Standards-Aligned National Identity Card");
  const [recipientWallet, setRecipientWallet] = useState("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266");
  const [recipientDid, setRecipientDid] = useState("did:key:z6MkuBesnaSecureHolder2026Ed25519");
  const [subjectName, setSubjectName] = useState("Charaf Eddine Bessanane");
  const [nationalId, setNationalId] = useState("TR-10293847561");
  const [nationality, setNationality] = useState("TUR");
  const [birthDate, setBirthDate] = useState("1999-04-12");

  const [assessingRisk, setAssessingRisk] = useState(false);
  const [riskAssessment, setRiskAssessment] = useState<any>(null);
  const [issuing, setIssuing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Poll OID4VCI offer status
  useEffect(() => {
    if (!oidOffer || offerClaimed) return;
    const interval = setInterval(async () => {
      try {
        const latest = await getOid4vciOffer(oidOffer.offerId);
        if (latest.status === "CLAIMED") {
          setOfferClaimed(true);
          setOidOffer(latest);
        }
      } catch (err) {
        // Silently retry polling
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [oidOffer, offerClaimed]);

  // Handle OID4VCI Offer Generation
  const handleGenerateOidOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeneratingOffer(true);
    setError(null);
    setOfferClaimed(false);

    try {
      const subjectData: Record<string, any> = {
        affiliation: oidAffiliation,
        programCode: oidProgramCode,
        degree: oidDegree,
        graduationYear: Number(oidGradYear),
      };

      const offer = await createOid4vciOffer({
        credentialConfigurationIds: [oidConfigId],
        subjectData,
        ttlSeconds: Number(oidTtlSeconds),
        userPin: oidUserPin.trim() || undefined,
      });

      setOidOffer(offer);
    } catch (err: any) {
      setError(err.message || "Failed to create OID4VCI offer.");
    } finally {
      setGeneratingOffer(false);
    }
  };

  // Evaluate risk via AI threat engine
  const handleAssessRisk = async () => {
    setAssessingRisk(true);
    setError(null);
    try {
      const assessment = await assessFraudRisk({
        wallet_address: recipientWallet,
        did_id: recipientDid,
        ip_address: "127.0.0.1",
        device_fingerprint: "device-sec-vault-browser-2026",
        recent_failed_attempts: 0,
      });
      setRiskAssessment(assessment);
    } catch (err: any) {
      setError("AI assessment failed or service unreachable: " + err.message);
    } finally {
      setAssessingRisk(false);
    }
  };

  // Submit direct issuance
  const handleIssueDirect = async (e: React.FormEvent) => {
    e.preventDefault();
    setIssuing(true);
    setError(null);

    const claims: Record<string, any> = {
      "Full Name": subjectName,
      Nationality: nationality,
      "National ID No": nationalId,
      "Birth Date": birthDate,
      "Assurance Level": "Prototype High LoA",
    };

    try {
      const res = await issueCredential({
        wallet_address: recipientWallet,
        did_id: recipientDid,
        credential_type: category + "Credential",
        title,
        category,
        claims,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Credential issuance failed.");
    } finally {
      setIssuing(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "880px" }}>
      <button
        onClick={() => navigate("/issuer")}
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
        Back to Dashboard
      </button>

      <div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Credential Issuance Engine
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Standards-aligned OID4VCI Draft 13 issuance with QR deep links & W3C Bitstring status anchoring.
        </p>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          padding: "4px",
          backgroundColor: "#0d131f",
          borderRadius: "12px",
          border: "1px solid #1f2937",
          width: "fit-content",
        }}
      >
        <button
          type="button"
          onClick={() => {
            setActiveTab("OID4VCI");
            setError(null);
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 18px",
            fontSize: "0.85rem",
            fontWeight: 700,
            borderRadius: "8px",
            border: "none",
            cursor: "pointer",
            backgroundColor: activeTab === "OID4VCI" ? "#2563eb" : "transparent",
            color: activeTab === "OID4VCI" ? "#ffffff" : "#94a3b8",
            transition: "all 0.2s ease",
          }}
        >
          <QrCode size={16} />
          OID4VCI Credential Offer (QR Flow)
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab("DIRECT");
            setError(null);
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 18px",
            fontSize: "0.85rem",
            fontWeight: 700,
            borderRadius: "8px",
            border: "none",
            cursor: "pointer",
            backgroundColor: activeTab === "DIRECT" ? "#2563eb" : "transparent",
            color: activeTab === "DIRECT" ? "#ffffff" : "#94a3b8",
            transition: "all 0.2s ease",
          }}
        >
          <Layers size={16} />
          Direct Push Issuance
        </button>
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

      {/* ======================================================== */}
      {/* TAB 1: OID4VCI OFFER FLOW */}
      {/* ======================================================== */}
      {activeTab === "OID4VCI" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {oidOffer ? (
            <div
              style={{
                backgroundColor: "#111827",
                borderRadius: "16px",
                border: "1px solid rgba(59, 130, 246, 0.3)",
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
                      backgroundColor: offerClaimed ? "rgba(16, 185, 129, 0.2)" : "rgba(59, 130, 246, 0.2)",
                      color: offerClaimed ? "#34d399" : "#60a5fa",
                    }}
                  >
                    {offerClaimed ? <CheckCircle2 size={24} /> : <QrCode size={24} />}
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 700, color: "#ffffff" }}>
                      {offerClaimed ? "Credential Successfully Claimed!" : "OID4VCI Credential Offer Active"}
                    </h3>
                    <p style={{ margin: "2px 0 0 0", fontSize: "0.8rem", color: "#94a3b8" }}>
                      {offerClaimed
                        ? "Holder wallet exchanged pre-authorized code and received signed W3C VC 2.0."
                        : "Scan with Holder Wallet or use the deep link to claim credential."}
                    </p>
                  </div>
                </div>

                <div
                  style={{
                    padding: "6px 14px",
                    borderRadius: "9999px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    backgroundColor: offerClaimed ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)",
                    color: offerClaimed ? "#34d399" : "#fbbf24",
                    border: `1px solid ${offerClaimed ? "rgba(16, 185, 129, 0.4)" : "rgba(245, 158, 11, 0.4)"}`,
                  }}
                >
                  {offerClaimed ? "STATUS: CLAIMED" : "STATUS: WAITING FOR HOLDER SCAN"}
                </div>
              </div>

              {/* QR and Metadata Grid */}
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
                  value={oidOffer.deepLinkUri}
                  size={210}
                  title="OID4VCI Offer QR"
                  subtitle="EUDI ARF / OpenID Specification"
                />

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Offer Identifier:</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#60a5fa" }}>
                      {oidOffer.offerId}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Pre-Authorized Code:</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#38bdf8" }}>
                      {oidOffer.preAuthorizedCode}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Offered Configuration:</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
                      {oidOffer.credentialConfigurationIds.join(", ")}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Expires At:</div>
                    <div style={{ fontSize: "0.8rem", color: "#cbd5e1" }}>
                      {new Date(oidOffer.expiresAt).toLocaleTimeString()} ({new Date(oidOffer.expiresAt).toLocaleDateString()})
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>Attested Claims:</div>
                    <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "2px" }}>
                      {Object.entries(oidOffer.subjectData).map(([k, v]) => `${k}: ${v}`).join(" | ")}
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  type="button"
                  onClick={() => setOidOffer(null)}
                  style={{
                    padding: "10px 18px",
                    borderRadius: "8px",
                    backgroundColor: "#2563eb",
                    color: "#ffffff",
                    fontWeight: 700,
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  Create Another Offer
                </button>
                <button
                  type="button"
                  onClick={() => navigate("/issuer")}
                  style={{
                    padding: "10px 18px",
                    borderRadius: "8px",
                    backgroundColor: "#1f2937",
                    color: "#cbd5e1",
                    border: "1px solid #374151",
                    cursor: "pointer",
                  }}
                >
                  Back to Issuer Portal
                </button>
              </div>
            </div>
          ) : (
            <form
              onSubmit={handleGenerateOidOffer}
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
                  Generate OpenID for Verifiable Credential Issuance Offer
                </h3>
              </div>

              {/* Credential Configuration */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Credential Profile / Configuration
                  </label>
                  <select
                    value={oidConfigId}
                    onChange={(e) => setOidConfigId(e.target.value)}
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
                      Qualified Electronic Attestation (QEAA Prototype)
                    </option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Affiliation Type
                  </label>
                  <select
                    value={oidAffiliation}
                    onChange={(e) => setOidAffiliation(e.target.value)}
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
                    <option value="student">student</option>
                    <option value="faculty">faculty</option>
                    <option value="staff">staff</option>
                  </select>
                </div>
              </div>

              {/* Subject Claims Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Program Code
                  </label>
                  <input
                    type="text"
                    value={oidProgramCode}
                    onChange={(e) => setOidProgramCode(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      backgroundColor: "#0d131f",
                      border: "1px solid #1f2937",
                      color: "#ffffff",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Degree Title
                  </label>
                  <select
                    value={oidDegree}
                    onChange={(e) => setOidDegree(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      backgroundColor: "#0d131f",
                      border: "1px solid #1f2937",
                      color: "#ffffff",
                      fontSize: "0.85rem",
                    }}
                  >
                    <option value="Bachelor of Science">Bachelor of Science</option>
                    <option value="Master of Science">Master of Science</option>
                    <option value="Doctor of Philosophy">Doctor of Philosophy</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Graduation Year
                  </label>
                  <input
                    type="number"
                    value={oidGradYear}
                    onChange={(e) => setOidGradYear(Number(e.target.value))}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      backgroundColor: "#0d131f",
                      border: "1px solid #1f2937",
                      color: "#ffffff",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>
              </div>

              {/* Offer Constraints */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px", borderTop: "1px solid #1f2937", paddingTop: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Offer Validity Window (Seconds)
                  </label>
                  <select
                    value={oidTtlSeconds}
                    onChange={(e) => setOidTtlSeconds(Number(e.target.value))}
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
                    <option value={900}>15 Minutes (900s)</option>
                    <option value={1800}>30 Minutes (1800s)</option>
                    <option value={3600}>1 Hour (3600s)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    User PIN Protection (Optional)
                  </label>
                  <input
                    type="password"
                    maxLength={8}
                    placeholder="Leave empty or enter 4-8 digit PIN"
                    value={oidUserPin}
                    onChange={(e) => setOidUserPin(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px",
                      borderRadius: "8px",
                      backgroundColor: "#0d131f",
                      border: "1px solid #1f2937",
                      color: "#ffffff",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={generatingOffer}
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: "10px",
                  backgroundColor: "#2563eb",
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
                {generatingOffer ? (
                  <span>Generating OID4VCI Offer & Deep Link...</span>
                ) : (
                  <>
                    <QrCode size={18} />
                    Generate OID4VCI Offer & QR Code
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 2: DIRECT ISSUANCE (LEGACY PROTOTYPE) */}
      {/* ======================================================== */}
      {activeTab === "DIRECT" && (
        <div>
          {result ? (
            <div
              style={{
                backgroundColor: "#111827",
                borderRadius: "16px",
                border: "1px solid rgba(16, 185, 129, 0.4)",
                padding: "24px",
                display: "flex",
                flexDirection: "column",
                gap: "16px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#34d399" }}>
                <CheckCircle2 size={28} />
                <div>
                  <h3 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                    Credential Issued & Anchored!
                  </h3>
                  <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "2px 0 0 0" }}>
                    Ed25519 linked data signature generated and Bitstring revocation slot allocated.
                  </p>
                </div>
              </div>

              <div style={{ backgroundColor: "#0d131f", padding: "14px", borderRadius: "10px", border: "1px solid #1f2937", fontSize: "0.8rem" }}>
                <div style={{ color: "#94a3b8" }}>Credential URN:</div>
                <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>
                  {result.credential_id || result.id || "urn:uuid:credential-success"}
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  onClick={() => {
                    setResult(null);
                    setRiskAssessment(null);
                  }}
                  style={{
                    padding: "10px 18px",
                    borderRadius: "8px",
                    backgroundColor: "#2563eb",
                    color: "#ffffff",
                    fontWeight: 700,
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  Issue Another Credential
                </button>
                <button
                  onClick={() => navigate("/issuer")}
                  style={{
                    padding: "10px 18px",
                    borderRadius: "8px",
                    backgroundColor: "#1f2937",
                    color: "#cbd5e1",
                    border: "1px solid #374151",
                    cursor: "pointer",
                  }}
                >
                  Back to Dashboard
                </button>
              </div>
            </div>
          ) : (
            <form
              onSubmit={handleIssueDirect}
              style={{
                backgroundColor: "#111827",
                borderRadius: "16px",
                border: "1px solid #1f2937",
                padding: "24px",
                display: "flex",
                flexDirection: "column",
                gap: "16px",
              }}
            >
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
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
                    <option value="IDENTITY">National Identity</option>
                    <option value="QUALIFIED">Higher Education Attestation</option>
                    <option value="FINANCE">Financial KYC Attestation</option>
                    <option value="HEALTH">Health & Medical Record</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Display Title
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px",
                      borderRadius: "8px",
                      backgroundColor: "#0d131f",
                      border: "1px solid #1f2937",
                      color: "#ffffff",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>
              </div>

              {/* Recipient Subject */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Recipient EVM Address
                  </label>
                  <input
                    type="text"
                    value={recipientWallet}
                    onChange={(e) => setRecipientWallet(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px",
                      borderRadius: "8px",
                      backgroundColor: "#0d131f",
                      border: "1px solid #1f2937",
                      color: "#ffffff",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8rem",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Recipient Subject DID
                  </label>
                  <input
                    type="text"
                    value={recipientDid}
                    onChange={(e) => setRecipientDid(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px",
                      borderRadius: "8px",
                      backgroundColor: "#0d131f",
                      border: "1px solid #1f2937",
                      color: "#ffffff",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8rem",
                    }}
                  />
                </div>
              </div>

              {/* Subject Claims */}
              <div style={{ borderTop: "1px solid #1f2937", paddingTop: "14px" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc", display: "block", marginBottom: "10px" }}>
                  Attested Subject Claims
                </span>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>Full Name</label>
                    <input
                      type="text"
                      value={subjectName}
                      onChange={(e) => setSubjectName(e.target.value)}
                      style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>National ID No</label>
                    <input
                      type="text"
                      value={nationalId}
                      onChange={(e) => setNationalId(e.target.value)}
                      style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>Nationality</label>
                    <input
                      type="text"
                      value={nationality}
                      onChange={(e) => setNationality(e.target.value)}
                      style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.72rem", color: "#94a3b8", marginBottom: "4px" }}>Birth Date</label>
                    <input
                      type="date"
                      value={birthDate}
                      onChange={(e) => setBirthDate(e.target.value)}
                      style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
                    />
                  </div>
                </div>
              </div>

              {/* AI Pre-Issuance Threat Check */}
              <div style={{ borderTop: "1px solid #1f2937", paddingTop: "14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>
                    AI Threat Assessment Gate
                  </span>
                  <button
                    type="button"
                    onClick={handleAssessRisk}
                    disabled={assessingRisk}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      backgroundColor: "#1f2937",
                      border: "1px solid #374151",
                      color: "#60a5fa",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {assessingRisk ? "Evaluating AI Model..." : "Run Pre-Issuance AI Check"}
                  </button>
                </div>

                {riskAssessment && (
                  <RiskScorePanel
                    score={riskAssessment.risk_score}
                    isFraudulent={riskAssessment.is_fraudulent}
                    xgboostProbability={riskAssessment.xgboost_probability}
                    reconstructionMse={riskAssessment.reconstruction_mse}
                    reasons={riskAssessment.reasons}
                  />
                )}
              </div>

              {/* Submit Action */}
              <button
                type="submit"
                disabled={issuing}
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: "10px",
                  backgroundColor: "#2563eb",
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
                {issuing ? (
                  <span>Signing with Ed25519 & Anchoring...</span>
                ) : (
                  <>
                    <Send size={16} />
                    Sign and Issue Verifiable Credential
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
};
