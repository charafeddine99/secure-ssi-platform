import React from "react";
import { TrustBadge } from "../../components/common/TrustBadge";
import { StatusChip } from "../../components/common/StatusChip";
import { History, ShieldCheck, FileCheck } from "lucide-react";

export const VerificationHistoryPage: React.FC = () => {
  const history = [
    {
      id: "VERIF-1049",
      timestamp: "2026-09-22 17:11:26",
      verifierAgent: "Airport E-Gate Border Inspector #1",
      holderDid: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
      credentialType: "NationalIdentityCredential",
      disclosedClaims: "Nationality: TUR, Assurance Level",
      predicateResult: "age >= 18: SATISFIED",
      status: "VERIFIED"
    },
    {
      id: "VERIF-1048",
      timestamp: "2026-09-22 14:40:12",
      verifierAgent: "Fintech Compliance KYC Desk",
      holderDid: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
      credentialType: "FinancialKYCCredential",
      disclosedClaims: "Account Holder, Tax ID, Risk Profile",
      predicateResult: "N/A",
      status: "VERIFIED"
    },
    {
      id: "VERIF-1047",
      timestamp: "2026-09-21 19:22:04",
      verifierAgent: "University Lab Turnstile",
      holderDid: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
      credentialType: "BachelorDiplomaCredential",
      disclosedClaims: "Student Name, Degree Program",
      predicateResult: "graduated == true: SATISFIED",
      status: "VERIFIED"
    }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Verification Audit Log & History
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Tamper-proof verifiable presentation logs recorded for institutional compliance audits.
        </p>
      </div>

      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #1f2937", color: "#94a3b8" }}>
                <th style={{ padding: "10px 12px" }}>Audit ID</th>
                <th style={{ padding: "10px 12px" }}>Timestamp</th>
                <th style={{ padding: "10px 12px" }}>Verifier Agent</th>
                <th style={{ padding: "10px 12px" }}>Credential Verified</th>
                <th style={{ padding: "10px 12px" }}>Predicate Proof</th>
                <th style={{ padding: "10px 12px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} style={{ borderBottom: "1px solid #1f2937" }}>
                  <td style={{ padding: "12px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>
                    {h.id}
                  </td>
                  <td style={{ padding: "12px", color: "#94a3b8" }}>
                    {h.timestamp}
                  </td>
                  <td style={{ padding: "12px", fontWeight: 600, color: "#f8fafc" }}>
                    {h.verifierAgent}
                  </td>
                  <td style={{ padding: "12px", color: "#cbd5e1" }}>
                    {h.credentialType}
                  </td>
                  <td style={{ padding: "12px", color: "#34d399", fontWeight: 500 }}>
                    {h.predicateResult}
                  </td>
                  <td style={{ padding: "12px" }}>
                    <StatusChip status={h.status} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
