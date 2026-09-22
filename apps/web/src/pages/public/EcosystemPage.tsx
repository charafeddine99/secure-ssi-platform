import React, { useState } from "react";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { Building2, Search, FileCode, CheckCircle2, Globe, Shield } from "lucide-react";

export const EcosystemPage: React.FC = () => {
  const [filter, setFilter] = useState<"ALL" | "ISSUERS" | "VERIFIERS" | "SCHEMAS">("ALL");

  const participants = [
    {
      name: "T.C. Nüfus ve Vatandaşlık İşleri (NVİ)",
      type: "ISSUER",
      did: "did:gov:eudi:nvi-authority",
      credentials: ["NationalIdentityCredential", "ResidencePermitCredential"],
      status: "ACTIVE",
      trustLevel: "STANDARDS_ALIGNED",
      location: "Ankara, TR"
    },
    {
      name: "Sakarya Uygulamalı Bilimler Üniversitesi (SUBÜ)",
      type: "ISSUER",
      did: "did:ssi:subu:academic-authority",
      credentials: ["BachelorDiplomaCredential", "StudentEnrollmentCredential"],
      status: "ACTIVE",
      trustLevel: "STANDARDS_ALIGNED",
      location: "Sakarya, TR"
    },
    {
      name: "Emniyet Genel Müdürlüğü Pasaport Dairesi",
      type: "ISSUER",
      did: "did:gov:egm:passport-registry",
      credentials: ["BiometricPassportCredential"],
      status: "ACTIVE",
      trustLevel: "STANDARDS_ALIGNED",
      location: "Ankara, TR"
    },
    {
      name: "European Border Control & E-Gates",
      type: "VERIFIER",
      did: "did:verifier:frontex:e-gate-check",
      credentials: ["BiometricPassportCredential", "NationalIdentityCredential"],
      status: "ACTIVE",
      trustLevel: "STANDARDS_ALIGNED",
      location: "Brussels, BE"
    },
    {
      name: "Banking KYC & AML Inspection Service",
      type: "VERIFIER",
      did: "did:verifier:fintech:kyc-inspection",
      credentials: ["FinancialKYCCredential", "NationalIdentityCredential"],
      status: "ACTIVE",
      trustLevel: "STANDARDS_ALIGNED",
      location: "Istanbul, TR"
    }
  ];

  const schemas = [
    {
      id: "https://schema.org/NationalIdentityCredential",
      name: "National Identity Credential",
      version: "2.0.0",
      claims: ["name", "nationalId", "birthDate", "nationality", "gender", "address"],
      proofType: "Ed25519Signature2020",
      status: "ACTIVE"
    },
    {
      id: "https://schema.org/BachelorDiplomaCredential",
      name: "Higher Education Degree Credential",
      version: "1.4.0",
      claims: ["studentName", "degreeTitle", "university", "faculty", "graduationYear", "gpa"],
      proofType: "Ed25519Signature2020",
      status: "ACTIVE"
    },
    {
      id: "https://schema.org/FinancialKYCCredential",
      name: "Banking & Financial Qualified KYC",
      version: "1.2.0",
      claims: ["accountHolder", "taxId", "amlRiskCategory", "verifiedIncomeRange", "bankCode"],
      proofType: "Ed25519Signature2020",
      status: "ACTIVE"
    }
  ];

  const filteredParticipants = participants.filter((p) => {
    if (filter === "ALL") return true;
    if (filter === "ISSUERS") return p.type === "ISSUER";
    if (filter === "VERIFIERS") return p.type === "VERIFIER";
    return false;
  });

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 24px" }}>
      <div style={{ marginBottom: "32px" }}>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "12px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>
        <h1 style={{ fontSize: "2.2rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Trust Ecosystem & Registry Directory
        </h1>
        <p style={{ fontSize: "0.95rem", color: "#94a3b8", marginTop: "6px" }}>
          Accredited institutional participants, trusted DID anchors, and standardized W3C VC 2.0 schemas.
        </p>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "24px", borderBottom: "1px solid #1f2937", paddingBottom: "12px" }}>
        {(["ALL", "ISSUERS", "VERIFIERS", "SCHEMAS"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "none",
              fontSize: "0.85rem",
              fontWeight: 600,
              cursor: "pointer",
              backgroundColor: filter === tab ? "#2563eb" : "#111827",
              color: filter === tab ? "#ffffff" : "#94a3b8"
            }}
          >
            {tab === "ALL" ? "All Entities" : tab === "ISSUERS" ? "Issuers (3)" : tab === "VERIFIERS" ? "Verifiers (2)" : "Credential Schemas (3)"}
          </button>
        ))}
      </div>

      {/* Entities Table */}
      {filter !== "SCHEMAS" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "40px" }}>
          {filteredParticipants.map((p) => (
            <div
              key={p.did}
              style={{
                backgroundColor: "#111827",
                border: "1px solid #1f2937",
                borderRadius: "12px",
                padding: "16px 20px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "16px"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                <div
                  style={{
                    padding: "12px",
                    borderRadius: "10px",
                    backgroundColor: p.type === "ISSUER" ? "rgba(37,99,235,0.1)" : "rgba(16,185,129,0.1)"
                  }}
                >
                  {p.type === "ISSUER" ? <Building2 size={24} color="#60a5fa" /> : <Search size={24} color="#34d399" />}
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                      {p.name}
                    </h3>
                    <StatusChip status={p.status} size="sm" />
                  </div>
                  <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "4px" }}>
                    {p.did}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "2px" }}>
                    {p.location} • Supported Credentials: {p.credentials.join(", ")}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Schemas Section */}
      {(filter === "ALL" || filter === "SCHEMAS") && (
        <div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, color: "#ffffff", marginBottom: "16px" }}>
            W3C JSON-LD Credential Schemas
          </h2>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "16px" }}>
            {schemas.map((s) => (
              <div
                key={s.id}
                style={{
                  backgroundColor: "#0d131f",
                  border: "1px solid #1f2937",
                  borderRadius: "12px",
                  padding: "18px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontSize: "0.7rem", color: "#60a5fa", fontFamily: "var(--font-mono)" }}>
                      v{s.version}
                    </span>
                    <StatusChip status={s.status} size="sm" />
                  </div>

                  <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#ffffff", margin: "0 0 8px 0" }}>
                    {s.name}
                  </h3>
                  <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#94a3b8", wordBreak: "break-all", marginBottom: "12px" }}>
                    {s.id}
                  </div>

                  <div style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>
                    <strong>Standard Attributes:</strong>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "6px" }}>
                      {s.claims.map((c) => (
                        <span
                          key={c}
                          style={{
                            padding: "2px 6px",
                            backgroundColor: "#161f33",
                            borderRadius: "4px",
                            fontSize: "0.7rem",
                            color: "#93c5fd"
                          }}
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #1f2937", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.72rem", color: "#64748b" }}>
                  <span>Proof: {s.proofType}</span>
                  <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
