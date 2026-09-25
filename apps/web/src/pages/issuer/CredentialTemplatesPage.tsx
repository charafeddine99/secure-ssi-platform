import React from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { FileText, PlusCircle, ArrowRight, Shield } from "lucide-react";

export const CredentialTemplatesPage: React.FC = () => {
  const navigate = useNavigate();

  const templates = [
    {
      id: "template-national-id",
      name: "Standards-Aligned National Identity Card",
      category: "IDENTITY",
      description: "Electronic national identification credential aligned with W3C VC 2.0 specifications.",
      defaultClaims: {
        "Full Name": "Subject Full Legal Name",
        "Nationality": "ISO 3166-1 alpha-3 code",
        "National ID No": "Alphanumeric identifier",
        "Birth Date": "YYYY-MM-DD",
        "Assurance Level": "Prototype High LoA"
      },
      validityYears: 10
    },
    {
      id: "template-academic-diploma",
      name: "Higher Education Degree Attestation",
      category: "QUALIFIED",
      description: "University degree qualification attestation with faculty, graduation year, and GPA.",
      defaultClaims: {
        "Student Name": "Graduate Name",
        "Degree Program": "e.g. Computer Engineering B.Sc.",
        "Department": "Academic Department",
        "Graduation GPA": "e.g. 3.84 / 4.00",
        "Graduation Year": "2026"
      },
      validityYears: 100
    },
    {
      id: "template-bank-kyc",
      name: "Open Banking Verified KYC Credential",
      category: "FINANCE",
      description: "Financial KYC verification credential for high-assurance banking operations.",
      defaultClaims: {
        "Account Holder": "Verified Customer Name",
        "Tax Registration": "National Tax Identifier",
        "KYC Verification Level": "Tier 3 Full Sovereign",
        "Risk Profile": "Low Risk (AML Cleared)"
      },
      validityYears: 1
    }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" />
          </div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
            Credential Templates & Schemas
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
            Pre-configured schemas for issuing standards-aligned W3C Verifiable Credentials.
          </p>
        </div>

        <button
          onClick={() => navigate("/issuer/issue")}
          style={{
            padding: "10px 18px",
            borderRadius: "8px",
            backgroundColor: "#2563eb",
            border: "none",
            color: "#ffffff",
            fontWeight: 700,
            fontSize: "0.85rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px"
          }}
        >
          <PlusCircle size={16} />
          Use Template to Issue
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "20px" }}>
        {templates.map((t) => (
          <div
            key={t.id}
            style={{
              backgroundColor: "#111827",
              borderRadius: "14px",
              border: "1px solid #1f2937",
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between"
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ fontSize: "0.7rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase" }}>
                  {t.category}
                </span>
                <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>
                  Valid for: {t.validityYears} yrs
                </span>
              </div>

              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: "0 0 6px 0" }}>
                {t.name}
              </h3>
              <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "0 0 16px 0", lineHeight: 1.5 }}>
                {t.description}
              </p>

              <div style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>
                <strong>Schema Field Structure:</strong>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "8px" }}>
                  {Object.entries(t.defaultClaims).map(([field, sample]) => (
                    <div
                      key={field}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        padding: "6px 10px",
                        backgroundColor: "#0d131f",
                        borderRadius: "6px",
                        border: "1px solid #1f2937",
                        fontSize: "0.72rem"
                      }}
                    >
                      <span style={{ fontWeight: 600, color: "#f8fafc" }}>{field}</span>
                      <span style={{ color: "#64748b" }}>{sample}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <button
              onClick={() => navigate("/issuer/issue")}
              style={{
                marginTop: "20px",
                padding: "8px 14px",
                borderRadius: "8px",
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
                color: "#60a5fa",
                fontSize: "0.8rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px"
              }}
            >
              <span>Instantiate Credential</span>
              <ArrowRight size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
