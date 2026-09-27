import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useWallet } from "../../context/WalletContext";
import { fetchCredentials, fetchPendingOffers, claimOid4vciOffer, Oid4vciOffer } from "../../services/api";
import { CredentialCard, CredentialCardData } from "../../components/credentials/CredentialCard";
import { CredentialDetailModal } from "../../components/credentials/CredentialDetailModal";
import { SelectiveDisclosureSheet } from "../../components/consent/SelectiveDisclosureSheet";
import { TrustBadge } from "../../components/common/TrustBadge";
import {
  QrCode,
  RefreshCw,
  ShieldCheck,
  AlertCircle,
  Inbox,
  CheckCircle2,
  XCircle,
  Clock,
  Building,
  FileCheck,
  Check
} from "lucide-react";

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

  // OID4VCI Pending Offers State (Sprint 9 Golden Path)
  const [pendingOffers, setPendingOffers] = useState<Oid4vciOffer[]>([]);
  const [loadingOffers, setLoadingOffers] = useState(false);
  const [selectedOfferForConsent, setSelectedOfferForConsent] = useState<Oid4vciOffer | null>(null);
  const [pinInput, setPinInput] = useState("");
  const [claiming, setClaiming] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Load real credentials from backend
  const loadCredentials = async () => {
    setLoading(true);
    try {
      const walletAddr = account || user?.walletAddress;
      const userDid = user?.did;
      const data = await fetchCredentials(userDid, walletAddr);
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

  // Load pending credential offers from authoritative OID4VCI endpoint
  const loadPendingOffers = async () => {
    setLoadingOffers(true);
    try {
      const offers = await fetchPendingOffers();
      setPendingOffers(offers.filter((o) => o.status === "PENDING"));
    } catch {
      // Keep silent on background check
    } finally {
      setLoadingOffers(false);
    }
  };

  useEffect(() => {
    loadCredentials();
    loadPendingOffers();
  }, [account, user]);

  const handleSyncAll = async () => {
    await Promise.all([loadCredentials(), loadPendingOffers()]);
  };

  // Reject offer and dismiss
  const handleRejectOffer = (offer: Oid4vciOffer) => {
    setPendingOffers((prev) => prev.filter((o) => o.offerId !== offer.offerId));
    setNotification({
      type: "success",
      message: `Offer ${offer.offerId} rejected and dismissed.`
    });
    setTimeout(() => setNotification(null), 4000);
  };

  // Open Consent Modal
  const handleOpenConsent = (offer: Oid4vciOffer) => {
    setSelectedOfferForConsent(offer);
    setPinInput("");
    setNotification(null);
  };

  // Explicit user consent claim action (real OID4VCI flow)
  const handleConfirmClaim = async () => {
    if (!selectedOfferForConsent) return;
    setClaiming(true);
    setNotification(null);
    try {
      const targetDid = user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519";
      await claimOid4vciOffer({
        preAuthorizedCode: selectedOfferForConsent.preAuthorizedCode,
        holderDid: targetDid,
        walletId: "wallet_holder_default",
        userPin: pinInput.trim() || undefined
      });

      // Remove claimed offer from pending list
      setPendingOffers((prev) => prev.filter((o) => o.offerId !== selectedOfferForConsent.offerId));
      setSelectedOfferForConsent(null);
      setNotification({
        type: "success",
        message: `Credential successfully claimed, signed, and persisted into your secure wallet!`
      });
      setTimeout(() => setNotification(null), 5000);
      // Immediately reload credentials from database
      await loadCredentials();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed to claim credential."
      });
    } finally {
      setClaiming(false);
    }
  };

  const categories = ["ALL", "IDENTITY", "QUALIFIED", "FINANCE"];

  const filtered = credentials.filter((c) => {
    if (activeCategory === "ALL") return true;
    return c.category.toUpperCase() === activeCategory;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Notification Banner */}
      {notification && (
        <div
          style={{
            padding: "10px 16px",
            borderRadius: "10px",
            backgroundColor: notification.type === "success" ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
            border: `1px solid ${notification.type === "success" ? "#10b981" : "#ef4444"}`,
            color: notification.type === "success" ? "#6ee7b7" : "#fca5a5",
            fontSize: "0.85rem",
            display: "flex",
            alignItems: "center",
            gap: "8px"
          }}
        >
          {notification.type === "success" ? <Check size={16} /> : <AlertCircle size={16} />}
          <span>{notification.message}</span>
        </div>
      )}

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
            onClick={handleSyncAll}
            disabled={loading || loadingOffers}
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
            <RefreshCw size={14} className={loading || loadingOffers ? "spin" : ""} />
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

      {/* Pending Credential Offers Section (OID4VCI Golden Path) */}
      {pendingOffers.length > 0 && (
        <div
          style={{
            backgroundColor: "#111827",
            borderRadius: "14px",
            border: "1px solid #3b82f6",
            padding: "16px",
            boxShadow: "0 0 15px rgba(59, 130, 246, 0.15)"
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "12px"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Inbox size={20} color="#60a5fa" />
              <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
                Pending Credential Offers ({pendingOffers.length})
              </h3>
            </div>
            <span
              style={{
                fontSize: "0.7rem",
                padding: "3px 8px",
                borderRadius: "6px",
                backgroundColor: "rgba(59, 130, 246, 0.2)",
                color: "#93c5fd",
                fontWeight: 600,
                textTransform: "uppercase"
              }}
            >
              Action Required
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {pendingOffers.map((offer) => (
              <div
                key={offer.offerId}
                style={{
                  backgroundColor: "#1e293b",
                  borderRadius: "10px",
                  border: "1px solid #334155",
                  padding: "14px"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Building size={14} color="#94a3b8" />
                      <span style={{ fontSize: "0.75rem", color: "#94a3b8", fontWeight: 500 }}>
                        {offer.credentialIssuer || "Verified European Trust Authority"}
                      </span>
                    </div>
                    <h4 style={{ margin: "4px 0 0 0", fontSize: "0.9rem", color: "#f8fafc", fontWeight: 600 }}>
                      {offer.credentialConfigurationIds.join(", ")}
                    </h4>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.7rem", color: "#f59e0b" }}>
                    <Clock size={12} />
                    <span>Expires: {new Date(offer.expiresAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                </div>

                {/* Claims Preview */}
                {offer.subjectData && Object.keys(offer.subjectData).length > 0 && (
                  <div
                    style={{
                      backgroundColor: "#0f172a",
                      borderRadius: "6px",
                      padding: "8px 10px",
                      margin: "8px 0 12px 0",
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: "6px",
                      fontSize: "0.75rem"
                    }}
                  >
                    {Object.entries(offer.subjectData).map(([k, v]) => (
                      <div key={k} style={{ color: "#cbd5e1" }}>
                        <span style={{ color: "#64748b" }}>{k}: </span>
                        <strong style={{ color: "#e2e8f0" }}>{String(v)}</strong>
                      </div>
                    ))}
                  </div>
                )}

                {/* Action Buttons */}
                <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                  <button
                    onClick={() => handleRejectOffer(offer)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      backgroundColor: "transparent",
                      color: "#f87171",
                      border: "1px solid #dc2626",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px"
                    }}
                  >
                    <XCircle size={14} />
                    Reject
                  </button>
                  <button
                    onClick={() => handleOpenConsent(offer)}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "6px",
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
                    <CheckCircle2 size={14} />
                    Review & Accept
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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

      {/* Explicit Consent Modal for OID4VCI Offer Claim */}
      {selectedOfferForConsent && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(4px)"
          }}
        >
          <div
            style={{
              backgroundColor: "#111827",
              border: "1px solid #1f2937",
              borderRadius: "16px",
              padding: "24px",
              width: "100%",
              maxWidth: "500px",
              color: "#f8fafc",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <FileCheck size={24} color="#3b82f6" />
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700 }}>
                Explicit Credential Consent
              </h3>
            </div>

            <p style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "16px", lineHeight: "1.4" }}>
              The issuing institution has generated a verifiable credential offer for your identity. Review the claims below before providing consent to store this credential in your cryptographic wallet.
            </p>

            <div style={{ backgroundColor: "#1f2937", padding: "12px", borderRadius: "10px", marginBottom: "16px" }}>
              <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>Issuing Authority:</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc", marginBottom: "10px" }}>
                {selectedOfferForConsent.credentialIssuer}
              </div>

              <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>Credential Profile:</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#38bdf8", marginBottom: "10px" }}>
                {selectedOfferForConsent.credentialConfigurationIds.join(", ")}
              </div>

              <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>Binding Holder DID:</div>
              <div style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "#a7f3d0", wordBreak: "break-all" }}>
                {user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519"}
              </div>
            </div>

            {/* Claims Table */}
            <div style={{ marginBottom: "16px" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#cbd5e1", marginBottom: "6px" }}>
                Credential Claims to be Bound:
              </div>
              <div style={{ maxHeight: "150px", overflowY: "auto", border: "1px solid #374151", borderRadius: "8px" }}>
                {Object.entries(selectedOfferForConsent.subjectData || {}).map(([key, val], idx) => (
                  <div
                    key={key}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "6px 10px",
                      fontSize: "0.75rem",
                      backgroundColor: idx % 2 === 0 ? "#111827" : "#1a2234",
                      borderBottom: "1px solid #2d3748"
                    }}
                  >
                    <span style={{ color: "#94a3b8" }}>{key}</span>
                    <span style={{ fontWeight: 600, color: "#f8fafc" }}>{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* PIN Input if required */}
            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "0.75rem", color: "#94a3b8", marginBottom: "4px" }}>
                User PIN (if provided by issuer):
              </label>
              <input
                type="password"
                placeholder="Enter PIN if required"
                value={pinInput}
                onChange={(e) => setPinInput(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  color: "#f8fafc",
                  fontSize: "0.85rem",
                  boxSizing: "border-box"
                }}
              />
            </div>

            {/* Consent Disclaimer */}
            <div
              style={{
                backgroundColor: "rgba(16, 185, 129, 0.1)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                padding: "8px 12px",
                borderRadius: "8px",
                fontSize: "0.75rem",
                color: "#6ee7b7",
                marginBottom: "16px"
              }}
            >
              ✓ I explicitly consent to accept this credential and bind it to my private DID key in accordance with W3C VC 2.0 &amp; OID4VCI specifications.
            </div>

            {/* Modal Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                onClick={() => setSelectedOfferForConsent(null)}
                disabled={claiming}
                style={{
                  padding: "8px 16px",
                  borderRadius: "8px",
                  backgroundColor: "#1f2937",
                  color: "#94a3b8",
                  border: "1px solid #374151",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmClaim}
                disabled={claiming}
                style={{
                  padding: "8px 20px",
                  borderRadius: "8px",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                {claiming ? <RefreshCw size={14} className="spin" /> : <CheckCircle2 size={14} />}
                {claiming ? "Claiming..." : "Accept & Claim"}
              </button>
            </div>
          </div>
        </div>
      )}

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
        onConfirmPresentation={(_disclosed, _blinded) => {
          navigate("/wallet/activity");
        }}
      />
    </div>
  );
};
