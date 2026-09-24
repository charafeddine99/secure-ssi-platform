import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import {
  claimOid4vciOffer,
} from "../../services/api";
import {
  QrCode,
  Camera,
  ShieldCheck,
  ArrowRight,
  CheckCircle2,
  Lock,
  Download,
  AlertCircle,
  ExternalLink,
  Sparkles,
} from "lucide-react";

export const ScanQrPage: React.FC = () => {
  const navigate = useNavigate();

  const [inputUri, setInputUri] = useState<string>("");
  const [claiming, setClaiming] = useState<boolean>(false);
  const [claimSuccess, setClaimSuccess] = useState<boolean>(false);
  const [claimedCredId, setClaimedCredId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const demoRequests = [
    {
      id: "EGATE",
      title: "European Border Control & E-Gates",
      purpose: "Automated citizenship clearance and active student verification.",
      uri: "openid4vp://?client_id=did:web:trust.eudi.europa.eu&request_uri=http://localhost:8000/api/v1/oid4vp/requests/session_egate_demo",
      type: "OID4VP",
    },
    {
      id: "CAMPUS_OFFER",
      title: "University Issuance Portal (OID4VCI)",
      purpose: "Higher Education Affiliation Credential Offer from accredited authority.",
      uri: "openid-credential-offer://?credential_offer=%7B%22credential_issuer%22%3A%22http%3A%2F%2Flocalhost%3A8001%22%2C%22credential_configuration_ids%22%3A%5B%22UniversityAffiliationCredential%22%5D%2C%22grants%22%3A%7B%22urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Apre-authorized_code%22%3A%7B%22pre-authorized_code%22%3A%22demo_code_12345%22%7D%7D%7D",
      type: "OID4VCI",
    },
  ];

  const handleProcessUri = async (uri: string) => {
    setError(null);
    setClaimSuccess(false);

    const trimmed = uri.trim();
    if (!trimmed) {
      setError("Please paste a valid openid-credential-offer:// or openid4vp:// URI.");
      return;
    }

    // 1. OID4VCI Offer Flow
    if (trimmed.startsWith("openid-credential-offer://")) {
      try {
        setClaiming(true);
        // Extract credential_offer param
        const url = new URL(trimmed.replace("openid-credential-offer://", "https://placeholder/"));
        const rawOffer = url.searchParams.get("credential_offer");
        let preAuthCode = "demo_code_12345";
        if (rawOffer) {
          const parsed = JSON.parse(decodeURIComponent(rawOffer));
          preAuthCode =
            parsed?.grants?.["urn:ietf:params:oauth:grant-type:pre-authorized_code"]?.["pre-authorized_code"] ||
            preAuthCode;
        }

        const holderDid =
          localStorage.getItem("ssi_user_did") ||
          "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP";

        const res = await claimOid4vciOffer({
          preAuthorizedCode: preAuthCode,
          holderDid,
          walletId: "wallet_holder_primary",
        });

        setClaimSuccess(true);
        setClaimedCredId(res.credentialId);
      } catch (err: any) {
        setError(err.message || "Failed to claim OID4VCI offer.");
      } finally {
        setClaiming(false);
      }
      return;
    }

    // 2. OID4VP Presentation Flow
    if (trimmed.startsWith("openid4vp://")) {
      try {
        const url = new URL(trimmed.replace("openid4vp://", "https://placeholder/"));
        const reqUri = url.searchParams.get("request_uri") || "";
        const parts = reqUri.split("/");
        const sessionId = parts[parts.length - 1] || "session_demo";

        navigate("/wallet/consent", {
          state: {
            sessionId,
            requestUri: trimmed,
          },
        });
      } catch (err: any) {
        setError("Failed to parse OID4VP URI: " + err.message);
      }
      return;
    }

    setError("Unrecognized QR protocol. Must start with openid-credential-offer:// or openid4vp://");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "680px", margin: "0 auto" }}>
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
        }}
      >
        {/* Simulated Camera Viewfinder */}
        <div
          style={{
            width: "200px",
            height: "200px",
            borderRadius: "20px",
            border: "2px dashed #2563eb",
            backgroundColor: "#070a12",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            marginBottom: "18px",
            boxShadow: "inset 0 0 20px rgba(37,99,235,0.15)",
          }}
        >
          <Camera size={36} color="#60a5fa" style={{ marginBottom: "8px" }} />
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            Scan OID4VCI / OID4VP QR
          </span>
          <div style={{ position: "absolute", top: "10px", right: "10px" }}>
            <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
          </div>
        </div>

        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#ffffff", margin: "0 0 6px 0" }}>
          Holder QR Scanner & Deep Link Dispatcher
        </h3>
        <p style={{ fontSize: "0.82rem", color: "#94a3b8", maxWidth: "420px", margin: "0 0 20px 0" }}>
          Scan an Issuer's Credential Offer QR to receive credentials, or scan a Verifier's Request QR to present credentials with selective disclosure.
        </p>

        {error && (
          <div
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#f87171",
              fontSize: "0.8rem",
              marginBottom: "16px",
              textAlign: "left",
            }}
          >
            {error}
          </div>
        )}

        {claimSuccess && (
          <div
            style={{
              width: "100%",
              padding: "16px",
              borderRadius: "12px",
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#34d399",
              fontSize: "0.85rem",
              marginBottom: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              textAlign: "left",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700 }}>
              <CheckCircle2 size={18} />
              Credential Successfully Claimed via OID4VCI!
            </div>
            <div style={{ fontSize: "0.75rem", color: "#94a3b8", fontFamily: "var(--font-mono)" }}>
              ID: {claimedCredId}
            </div>
            <button
              type="button"
              onClick={() => navigate("/wallet")}
              style={{
                marginTop: "4px",
                padding: "8px 14px",
                borderRadius: "6px",
                backgroundColor: "#059669",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.8rem",
                border: "none",
                cursor: "pointer",
                width: "fit-content",
              }}
            >
              View in Wallet Vault →
            </button>
          </div>
        )}

        {/* Manual URI Input */}
        <div style={{ width: "100%", display: "flex", gap: "8px", marginBottom: "20px" }}>
          <input
            type="text"
            placeholder="Paste openid-credential-offer:// or openid4vp:// URI..."
            value={inputUri}
            onChange={(e) => setInputUri(e.target.value)}
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: "8px",
              backgroundColor: "#0d131f",
              border: "1px solid #1f2937",
              color: "#ffffff",
              fontSize: "0.8rem",
              fontFamily: "var(--font-mono)",
            }}
          />
          <button
            type="button"
            onClick={() => handleProcessUri(inputUri)}
            disabled={claiming}
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.85rem",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            {claiming ? "Processing..." : "Process URI"}
          </button>
        </div>

        {/* Demo Fast Triggers */}
        <div style={{ width: "100%", textAlign: "left", borderTop: "1px solid #1f2937", paddingTop: "16px" }}>
          <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#94a3b8", display: "block", marginBottom: "10px" }}>
            Or test with one-click protocol samples:
          </span>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {demoRequests.map((req) => (
              <div
                key={req.id}
                onClick={() => {
                  setInputUri(req.uri);
                  handleProcessUri(req.uri);
                }}
                style={{
                  padding: "12px 14px",
                  borderRadius: "10px",
                  backgroundColor: "#0d131f",
                  border: "1px solid #1f2937",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  transition: "all 0.15s ease",
                }}
              >
                <div>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
                    {req.title}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "2px" }}>
                    {req.purpose}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#60a5fa", fontSize: "0.75rem", fontWeight: 600 }}>
                  <span>{req.type}</span>
                  <ArrowRight size={14} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
