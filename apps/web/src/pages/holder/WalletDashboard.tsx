import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useWallet } from "../../context/WalletContext";
import { fetchCredentials, BackendCredential } from "../../services/api";
import { CredentialCard, CredentialCardData } from "../../components/credentials/CredentialCard";
import { CredentialDetailModal } from "../../components/credentials/CredentialDetailModal";
import { SelectiveDisclosureSheet } from "../../components/consent/SelectiveDisclosureSheet";
import { TrustBadge } from "../../components/common/TrustBadge";
import { QrCode, PlusCircle, RefreshCw, ShieldCheck, AlertCircle } from "lucide-react";

// Standards-aligned fallback credentials (Academic Prototype)
const FALLBACK_CREDENTIALS: CredentialCardData[] = [
  {
    id: "urn:uuid:natid-prototype-2026-tr",
    title: "Standards-Aligned National Identity",
    category: "IDENTITY",
    issuer: "did:gov:eudi:nvi-authority",
    issuerName: "T.C. Nüfus ve Vatandaşlık İşleri (Prototype)",
    issuedDate: "2025-01-15",
    expiryDate: "2035-01-15",
    status: "ACTIVE",
    statusListIndex: 104,
    claims: {
      "Full Name": "Charaf Eddine Bessanane",
      "Nationality": "TUR",
      "National ID No": "TR-10293847561",
      "Birth Date": "1999-04-12",
      "Assurance Level": "Prototype High LoA",
      "Document No": "A92K81029"
    },
    proofValue: "z3s9PqRtXvM8EUDINationalIdentityProof2026Ed25519Signature",
    aiRiskScore: 5
  },
  {
    id: "urn:uuid:subu-diploma-2026-b210",
    title: "Academic Degree Attestation",
    category: "QUALIFIED",
    issuer: "did:ssi:subu:academic-authority",
    issuerName: "Sakarya University of Applied Sciences (SUBÜ)",
    issuedDate: "2026-06-30",
    expiryDate: "2036-06-30",
    status: "ACTIVE",
    statusListIndex: 105,
    claims: {
      "Student Name": "Charaf Eddine Bessanane",
      "Degree Program": "Computer Engineering B.Sc.",
      "Department": "Department of Computer Engineering",
      "Graduation GPA": "3.84 / 4.00",
      "Graduation Year": "2026"
    },
    proofValue: "z5aK8xW9mNpQrTuVwYzSUBUEngineeringDegree2026Ed25519",
    aiRiskScore: 8
  },
  {
    id: "urn:uuid:bank-kyc-attest-2026",
    title: "Qualified Financial KYC Credential",
    category: "FINANCE",
    issuer: "did:bank:open-banking:kyc-authority",
    issuerName: "Open Banking Financial Identity Authority",
    issuedDate: "2026-02-10",
    expiryDate: "2027-02-10",
    status: "ACTIVE",
    statusListIndex: 106,
    claims: {
      "Account Holder": "Charaf Eddine Bessanane",
      "KYC Verification Level": "Tier 3 Full Sovereign",
      "Tax Registration": "TR-9823419082",
      "Risk Profile": "Low Risk (AML Cleared)"
    },
    proofValue: "z7mPqRtXvM8BankKYCProof2026Ed25519Signature",
    aiRiskScore: 12
  }
];

export const WalletDashboard: React.FC = () => {
  const { user } = useAuth();
  const { account } = useWallet();
  const navigate = useNavigate();

  const [credentials, setCredentials] = useState<CredentialCardData[]>(FALLBACK_CREDENTIALS);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>("ALL");
  const [selectedCredForDetail, setSelectedCredForDetail] = useState<CredentialCardData | null>(null);
  const [selectedCredForConsent, setSelectedCredForConsent] = useState<CredentialCardData | null>(null);

  // Load real credentials from backend
  const loadCredentials = async () => {
    setLoading(true);
    try {
      const walletAddr = account || user?.walletAddress;
      const data = await fetchCredentials(walletAddr);
      if (data && data.length > 0) {
        const mapped: CredentialCardData[] = data.map((d) => ({
          id: d.id,
          title: d.title,
          category: d.category || "IDENTITY",
          issuer: d.issuer,
          issuerName: d.issuer_name,
          issuedDate: d.issued_date,
          expiryDate: d.expiry_date,
          status: d.status,
          claims: d.claims || {},
          proofValue: d.proof_value,
          aiRiskScore: d.ai_risk_score,
          statusListIndex: 104
        }));
        setCredentials(mapped);
      }
    } catch {
      // Keep fallbacks on network error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCredentials();
  }, [account, user]);

  const categories = ["ALL", "IDENTITY", "QUALIFIED", "FINANCE"];

  const filtered = credentials.filter((c) => {
    if (activeCategory === "ALL") return true;
    return c.category.toUpperCase() === activeCategory;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Quick Action Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          backgroundColor: "#111827",
          padding: "12px 16px",
          borderRadius: "14px",
          border: "1px solid #1f2937"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <ShieldCheck size={18} color="#34d399" />
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>
            {credentials.length} Verifiable Credentials
          </span>
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={loadCredentials}
            disabled={loading}
            title="Refresh from Database"
            style={{
              padding: "6px 10px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              color: "#94a3b8",
              border: "1px solid #374151",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px"
            }}
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            Sync
          </button>

          <button
            onClick={() => navigate("/wallet/scan")}
            style={{
              padding: "6px 12px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px"
            }}
          >
            <QrCode size={14} />
            Scan Request
          </button>
        </div>
      </div>

      {/* Category Pills */}
      <div style={{ display: "flex", gap: "6px", overflowX: "auto", paddingBottom: "4px" }}>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            style={{
              padding: "6px 14px",
              borderRadius: "9999px",
              fontSize: "0.75rem",
              fontWeight: 600,
              border: "none",
              cursor: "pointer",
              backgroundColor: activeCategory === cat ? "#2563eb" : "#111827",
              color: activeCategory === cat ? "#ffffff" : "#94a3b8",
              transition: "all 0.15s ease"
            }}
          >
            {cat === "ALL" ? "All Credentials" : cat}
          </button>
        ))}
      </div>

      {/* Credential Cards List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {filtered.map((cred) => (
          <CredentialCard
            key={cred.id}
            credential={cred}
            onViewDetails={(c) => setSelectedCredForDetail(c)}
            onPresent={(c) => setSelectedCredForConsent(c)}
          />
        ))}

        {filtered.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: "40px 20px",
              backgroundColor: "#111827",
              borderRadius: "14px",
              border: "1px solid #1f2937",
              color: "#94a3b8"
            }}
          >
            <AlertCircle size={32} color="#64748b" style={{ margin: "0 auto 10px auto" }} />
            <p style={{ margin: 0, fontSize: "0.9rem" }}>No credentials in this category.</p>
          </div>
        )}
      </div>

      {/* Modals */}
      <CredentialDetailModal
        credential={selectedCredForDetail}
        isOpen={!!selectedCredForDetail}
        onClose={() => setSelectedCredForDetail(null)}
      />

      <SelectiveDisclosureSheet
        credential={selectedCredForConsent}
        isOpen={!!selectedCredForConsent}
        onClose={() => setSelectedCredForConsent(null)}
        verifierName="European Airport Border Control E-Gate"
        verifierPurpose="Age verification (Over 18) and nationality validation"
        requiredClaims={["Nationality", "Uyruk"]}
        onConfirmPresentation={(disclosed, blinded) => {
          navigate("/wallet/activity");
        }}
      />
    </div>
  );
};
