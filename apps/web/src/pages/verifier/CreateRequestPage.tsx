import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { PlusCircle, QrCode, ArrowLeft, CheckCircle2, Copy, Check } from "lucide-react";

export const CreateRequestPage: React.FC = () => {
  const navigate = useNavigate();

  const [purpose, setPurpose] = useState("Age verification and citizenship confirmation");
  const [credentialType, setCredentialType] = useState("NationalIdentityCredential");
  const [predicate, setPredicate] = useState("age >= 18");
  const [claims, setClaims] = useState(["Nationality"]);
  const [generatedRequest, setGeneratedRequest] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  const availableClaims = [
    "Nationality",
    "Full Name",
    "National ID No",
    "Birth Date",
    "Student ID",
    "Graduation GPA"
  ];

  const toggleClaim = (c: string) => {
    if (claims.includes(c)) setClaims(claims.filter((item) => item !== c));
    else setClaims([...claims, c]);
  };

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    const req = {
      type: "VerifiablePresentationRequest",
      spec: "OID4VP 1.0 Draft",
      presentation_definition: {
        id: `req-${Date.now()}`,
        input_descriptors: [
          {
            id: credentialType,
            purpose: purpose,
            schema: [{ uri: `https://schema.org/${credentialType}` }],
            constraints: {
              fields: claims.map((c) => ({ path: [`$.credentialSubject.${c}`] })),
              predicate: predicate !== "none" ? predicate : undefined
            }
          }
        ]
      },
      client_id: "did:verifier:platform:compliance-office",
      nonce: Math.random().toString(36).substring(2, 15)
    };
    setGeneratedRequest(req);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(generatedRequest, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "840px" }}>
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
          padding: 0
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
          Create OID4VP Presentation Request
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Define verifier requirements, predicate conditions, and data minimization constraints.
        </p>
      </div>

      {generatedRequest ? (
        <div
          style={{
            backgroundColor: "#111827",
            borderRadius: "16px",
            border: "1px solid #1f2937",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "16px"
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#34d399" }}>
              <CheckCircle2 size={24} />
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "#ffffff" }}>
                OID4VP Request Ready for Presentation
              </h3>
            </div>

            <button
              onClick={handleCopy}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                padding: "6px 12px",
                borderRadius: "6px",
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                color: "#e2e8f0",
                fontSize: "0.75rem",
                cursor: "pointer"
              }}
            >
              {copied ? <Check size={14} color="#34d399" /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy Payload"}
            </button>
          </div>

          <pre
            style={{
              margin: 0,
              padding: "16px",
              backgroundColor: "#070a12",
              borderRadius: "10px",
              border: "1px solid #1f2937",
              color: "#38bdf8",
              fontFamily: "var(--font-mono)",
              fontSize: "0.78rem",
              overflowX: "auto"
            }}
          >
            {JSON.stringify(generatedRequest, null, 2)}
          </pre>

          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => navigate("/verifier/verify")}
              style={{
                padding: "10px 18px",
                borderRadius: "8px",
                backgroundColor: "#059669",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "0.85rem",
                border: "none",
                cursor: "pointer"
              }}
            >
              Test Verification Against This Request
            </button>

            <button
              onClick={() => setGeneratedRequest(null)}
              style={{
                padding: "10px 18px",
                borderRadius: "8px",
                backgroundColor: "#1f2937",
                color: "#e2e8f0",
                border: "1px solid #374151",
                cursor: "pointer"
              }}
            >
              Configure Another Request
            </button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={handleGenerate}
          style={{
            backgroundColor: "#111827",
            borderRadius: "16px",
            border: "1px solid #1f2937",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "16px"
          }}
        >
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
              Verification Purpose
            </label>
            <input
              type="text"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Required Credential Schema
              </label>
              <select
                value={credentialType}
                onChange={(e) => setCredentialType(e.target.value)}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
              >
                <option value="NationalIdentityCredential">National Identity Credential</option>
                <option value="BachelorDiplomaCredential">Bachelor Degree Credential</option>
                <option value="FinancialKYCCredential">Financial KYC Credential</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                Zero-Knowledge Predicate Rule
              </label>
              <select
                value={predicate}
                onChange={(e) => setPredicate(e.target.value)}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#0d131f", border: "1px solid #1f2937", color: "#ffffff", fontSize: "0.85rem" }}
              >
                <option value="age >= 18">Age Condition: age &gt;= 18 (Birth Date Hidden)</option>
                <option value="status == 'ACTIVE'">Status Condition: status == 'ACTIVE'</option>
                <option value="none">No predicate rule (Direct Claims)</option>
              </select>
            </div>
          </div>

          {/* Requested Claims */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "6px" }}>
              Select Explicit Claims Required:
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "8px" }}>
              {availableClaims.map((c) => {
                const checked = claims.includes(c);
                return (
                  <label
                    key={c}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      backgroundColor: checked ? "rgba(37,99,235,0.1)" : "#0d131f",
                      border: checked ? "1px solid rgba(37,99,235,0.4)" : "1px solid #1f2937",
                      cursor: "pointer",
                      fontSize: "0.82rem",
                      color: "#f8fafc"
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleClaim(c)}
                      style={{ accentColor: "#2563eb" }}
                    />
                    {c}
                  </label>
                );
              })}
            </div>
          </div>

          <button
            type="submit"
            style={{
              padding: "12px",
              borderRadius: "10px",
              backgroundColor: "#059669",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.9rem",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              marginTop: "8px"
            }}
          >
            <PlusCircle size={16} />
            Generate Presentation Request (OID4VP)
          </button>
        </form>
      )}
    </div>
  );
};
