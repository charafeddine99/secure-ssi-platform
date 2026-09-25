import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { TrustBadge } from "../../components/common/TrustBadge";
import { KeyRound, Shield, Eye, EyeOff, Users, Copy, Check } from "lucide-react";

export const SecuritySettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [showSeed, setShowSeed] = useState(false);
  const [copied, setCopied] = useState(false);

  const seedPhrase = user?.seedPhrase || "apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard";

  const handleCopy = () => {
    navigator.clipboard.writeText(seedPhrase);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const guardians = [
    { name: "Family Guardian", address: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", role: "Primary Trusted Contact" },
    { name: "Institutional Notary", address: "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", role: "Accredited Recovery Agent" },
    { name: "Hardware Security Vault", address: "0x90F79bf6EB2c4f870365E785982E1f101E93b906", role: "Offline Cold Signer" }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Sovereign Identity Overview */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <KeyRound size={20} color="#60a5fa" />
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
              Sovereign Key Management
            </h2>
          </div>
          <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.8rem" }}>
          <div style={{ backgroundColor: "#0d131f", padding: "10px 12px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ color: "#94a3b8" }}>Decentralized Identifier (DID):</span>
            <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px", wordBreak: "break-all" }}>
              {user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519"}
            </div>
          </div>

          <div style={{ backgroundColor: "#0d131f", padding: "10px 12px", borderRadius: "8px", border: "1px solid #1f2937" }}>
            <span style={{ color: "#94a3b8" }}>EVM Wallet Address:</span>
            <div style={{ fontFamily: "var(--font-mono)", color: "#c084fc", marginTop: "2px" }}>
              {user?.walletAddress || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"}
            </div>
          </div>
        </div>
      </div>

      {/* 12-Word Seed Backup */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                12-Word Recovery Seed Phrase
              </h3>
              <span
                style={{
                  fontSize: "0.65rem",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  backgroundColor: "#451a03",
                  color: "#f59e0b",
                  border: "1px solid #78350f",
                  fontWeight: 600
                }}
              >
                DEMO ARTIFACT — SIMULATED CUSTODY
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
              Simulated BIP-39 mnemonic phrase for academic evaluation. In production sovereign custody, raw seed phrases are never stored in databases or exposed in plaintext; keys remain in TEE/Secure Enclave hardware with Shamir SSS guardian recovery.
            </p>
          </div>
          <button
            onClick={() => setShowSeed(!showSeed)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 8px",
              borderRadius: "6px",
              border: "1px solid #374151",
              backgroundColor: "#1f2937",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: "0.75rem"
            }}
          >
            {showSeed ? <EyeOff size={14} /> : <Eye size={14} />}
            {showSeed ? "Hide" : "Reveal"}
          </button>
        </div>

        {showSeed ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "8px",
              backgroundColor: "#070a12",
              padding: "14px",
              borderRadius: "10px",
              border: "1px solid #1f2937",
              marginBottom: "12px"
            }}
          >
            {seedPhrase.split(" ").map((w, idx) => (
              <div
                key={idx}
                style={{
                  fontSize: "0.75rem",
                  fontFamily: "var(--font-mono)",
                  color: "#38bdf8",
                  padding: "4px 8px",
                  backgroundColor: "#111827",
                  borderRadius: "6px"
                }}
              >
                <span style={{ color: "#64748b", marginRight: "4px" }}>{idx + 1}.</span>
                {w}
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              backgroundColor: "#070a12",
              padding: "20px",
              borderRadius: "10px",
              border: "1px solid #1f2937",
              textAlign: "center",
              color: "#64748b",
              fontSize: "0.8rem",
              marginBottom: "12px"
            }}
          >
            •••••••• •••••••• •••••••• •••••••• •••••••• ••••••••
          </div>
        )}

        {showSeed && (
          <button
            onClick={handleCopy}
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "8px",
              backgroundColor: "#1f2937",
              color: "#e2e8f0",
              border: "1px solid #374151",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            {copied ? <Check size={14} color="#34d399" /> : <Copy size={14} />}
            {copied ? "Seed Phrase Copied" : "Copy Seed Phrase"}
          </button>
        )}
      </div>

      {/* Configured Social Guardians */}
      <div
        style={{
          backgroundColor: "#111827",
          borderRadius: "16px",
          border: "1px solid #1f2937",
          padding: "20px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Users size={18} color="#fbbf24" />
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", margin: 0 }}>
              EIP-4337 Social Guardians (2-of-3 Quorum)
            </h3>
          </div>
          <span style={{ fontSize: "0.7rem", color: "#34d399", fontWeight: 600 }}>
            Configured on EVM
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {guardians.map((g, i) => (
            <div
              key={i}
              style={{
                backgroundColor: "#0d131f",
                padding: "10px 12px",
                borderRadius: "8px",
                border: "1px solid #1f2937"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#f8fafc" }}>
                  {g.name}
                </span>
                <span style={{ fontSize: "0.7rem", color: "#60a5fa" }}>{g.role}</span>
              </div>
              <div style={{ fontSize: "0.7rem", fontFamily: "var(--font-mono)", color: "#94a3b8", marginTop: "2px" }}>
                {g.address}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
