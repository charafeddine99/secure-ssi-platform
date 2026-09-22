import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrustBadge } from "../../components/common/TrustBadge";
import { QrCode, Camera, ShieldCheck, ArrowRight, CheckCircle2, Lock } from "lucide-react";

export const ScanQrPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedDemoRequest, setSelectedDemoRequest] = useState<string>("EGATE");

  const demoRequests = [
    {
      id: "EGATE",
      verifier: "European Border Control & E-Gates (Demo)",
      purpose: "Automated age check (Age >= 18) and nationality validation for transit clearance.",
      requiredClaims: ["Nationality", "Uyruk"],
      predicate: "age >= 18"
    },
    {
      id: "BANK_KYC",
      verifier: "Fintech Open Banking Verification Service (Demo)",
      purpose: "Identity proof and AML status check for instant bank account opening.",
      requiredClaims: ["Full Name", "National ID No", "Tax Registration"],
      predicate: "none"
    },
    {
      id: "CAMPUS_ACCESS",
      verifier: "University Library & Laboratory Access Turnstile",
      purpose: "Verification of active student enrollment status for building entry.",
      requiredClaims: ["Student Name", "Degree Program"],
      predicate: "status == 'ACTIVE'"
    }
  ];

  const handleProceed = () => {
    navigate("/wallet/consent", { state: { requestId: selectedDemoRequest } });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center"
        }}
      >
        {/* Simulated Camera Viewfinder */}
        <div
          style={{
            width: "220px",
            height: "220px",
            borderRadius: "20px",
            border: "2px dashed #2563eb",
            backgroundColor: "#070a12",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            marginBottom: "20px",
            boxShadow: "inset 0 0 20px rgba(37,99,235,0.15)"
          }}
        >
          <Camera size={36} color="#60a5fa" style={{ marginBottom: "8px" }} />
          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            Scan OID4VP QR Code
          </span>
          <div
            style={{
              position: "absolute",
              top: "10px",
              right: "10px"
            }}
          >
            <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
          </div>
        </div>

        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: "0 0 6px 0" }}>
          Scan Verification Request
        </h3>
        <p style={{ fontSize: "0.8rem", color: "#94a3b8", maxWidth: "380px", margin: "0 0 20px 0" }}>
          Point camera at a verifier QR code or select a pre-configured OID4VP test request below:
        </p>

        {/* Demo Request Selector */}
        <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "10px", marginBottom: "20px" }}>
          {demoRequests.map((req) => (
            <div
              key={req.id}
              onClick={() => setSelectedDemoRequest(req.id)}
              style={{
                textAlign: "left",
                padding: "12px 14px",
                borderRadius: "10px",
                backgroundColor: selectedDemoRequest === req.id ? "rgba(37, 99, 235, 0.12)" : "#0d131f",
                border: selectedDemoRequest === req.id ? "1px solid #2563eb" : "1px solid #1f2937",
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>
                  {req.verifier}
                </span>
                {selectedDemoRequest === req.id && <CheckCircle2 size={16} color="#34d399" />}
              </div>
              <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
                {req.purpose}
              </p>
            </div>
          ))}
        </div>

        <button
          onClick={handleProceed}
          style={{
            width: "100%",
            padding: "12px",
            borderRadius: "10px",
            backgroundColor: "#2563eb",
            color: "#ffffff",
            fontWeight: 700,
            fontSize: "0.9rem",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px"
          }}
        >
          <span>Open Consent & Selective Disclosure</span>
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
};
