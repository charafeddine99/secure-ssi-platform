import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { TrustBadge } from "../../components/common/TrustBadge";
import { 
  ShieldCheck, 
  Cpu, 
  Layers, 
  KeyRound, 
  Lock, 
  Building2, 
  Search, 
  Users, 
  Settings, 
  ArrowRight,
  CheckCircle2,
  FileCode,
  Database
} from "lucide-react";

export const LandingPage: React.FC = () => {
  const { switchDemoRole } = useAuth();
  const navigate = useNavigate();

  const handleRoleLaunch = (role: "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN", path: string) => {
    switchDemoRole(role);
    navigate(path);
  };

  const coreFeatures = [
    {
      title: "W3C VC 2.0 & Ed25519 Cryptography",
      description: "Standards-aligned verifiable credentials canonicalized via RFC 8785 (JCS) and signed with Ed25519 cryptographic linked data proofs.",
      icon: KeyRound,
      color: "#60a5fa"
    },
    {
      title: "User Consent & Data Minimization",
      description: "Interactive selective disclosure sheets allow holders to reveal only necessary claims while computing salted blinded commitments for hidden fields.",
      icon: Lock,
      color: "#34d399"
    },
    {
      title: "Hybrid AI Threat Engine",
      description: "Dual-model threat detection combining XGBoost-inspired gradient boosted tree splits with Autoencoder reconstruction MSE for real-time anomaly mitigation.",
      icon: Cpu,
      color: "#f87171"
    },
    {
      title: "Blockchain Trust Anchoring",
      description: "Decentralized trust registry anchored on Ethereum testnets via OpenZeppelin smart contracts (DIDRegistry, EmergencyRecovery, RevocationRegistry).",
      icon: Database,
      color: "#c084fc"
    },
    {
      title: "EIP-4337 Social Recovery Quorum",
      description: "M-of-N guardian consensus threshold (2-of-3 / 3-of-5) enabling key rotation and emergency wallet recovery without centralized custodians.",
      icon: Users,
      color: "#fbbf24"
    },
    {
      title: "EUDI ARF-Inspired Architecture",
      description: "Domain-agnostic identity design modeled after European Digital Identity Architecture and Reference Framework (Academic Prototype).",
      icon: Layers,
      color: "#38bdf8"
    }
  ];

  const portals = [
    {
      role: "HOLDER" as const,
      title: "Holder Wallet",
      subtitle: "Personal Sovereign Identity & Credential Vault",
      desc: "Tactile digital credential cards, QR presentation, and granular selective disclosure consent.",
      icon: ShieldCheck,
      path: "/wallet",
      accent: "#2563eb",
      badge: "Mobile-First"
    },
    {
      role: "ISSUER" as const,
      title: "Issuer Console",
      subtitle: "Institutional Credential Issuance & Status",
      desc: "Issue W3C VC 2.0 credentials with pre-issuance AI threat evaluation and on-chain bitstring anchoring.",
      icon: Building2,
      path: "/issuer",
      accent: "#1d4ed8",
      badge: "Institutional"
    },
    {
      role: "VERIFIER" as const,
      title: "Verifier Service",
      subtitle: "Presentation Request & Cryptographic Audit",
      desc: "Validate Ed25519 signatures, revocation bitstrings, and selective disclosure claims in sub-millisecond speeds.",
      icon: Search,
      path: "/verifier",
      accent: "#059669",
      badge: "Verification-Centric"
    },
    {
      role: "GUARDIAN" as const,
      title: "Guardian Recovery",
      subtitle: "EIP-4337 Multi-Sig Social Recovery",
      desc: "Participate in M-of-N quorum threshold signing to securely rotate keys for compromised or lost wallets.",
      icon: Users,
      path: "/guardian",
      accent: "#d97706",
      badge: "Security Quorum"
    },
    {
      role: "ADMIN" as const,
      title: "System Admin Cockpit",
      subtitle: "Infrastructure, Blockchain & AI Telemetry",
      desc: "Live microservice metrics, smart contract interaction feeds, and real-time AI anomaly stream.",
      icon: Settings,
      path: "/admin",
      accent: "#7c3aed",
      badge: "Operations"
    }
  ];

  return (
    <div style={{ maxWidth: "1240px", margin: "0 auto", padding: "48px 24px" }}>
      {/* Hero Section */}
      <div style={{ textAlign: "center", marginBottom: "60px" }}>
        <div style={{ display: "inline-flex", gap: "8px", alignItems: "center", marginBottom: "16px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="BLOCKCHAIN_ANCHORED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>

        <h1
          style={{
            fontSize: "clamp(2.2rem, 5vw, 3.4rem)",
            fontWeight: 800,
            letterSpacing: "-0.03em",
            color: "#ffffff",
            lineHeight: 1.15,
            maxWidth: "920px",
            margin: "0 auto 20px auto"
          }}
        >
          Secure Self-Sovereign Identity <br />
          <span style={{ background: "linear-gradient(135deg, #60a5fa 0%, #3b82f6 50%, #93c5fd 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Academic Platform Reference Implementation
          </span>
        </h1>

        <p
          style={{
            fontSize: "1.1rem",
            color: "#94a3b8",
            maxWidth: "760px",
            margin: "0 auto 32px auto",
            lineHeight: 1.6
          }}
        >
          An end-to-end decentralized identity system bridging W3C Verifiable Credentials 2.0, 
          EUDI ARF-inspired wallet workflows, AI-driven fraud anomaly mitigation, 
          and Ethereum smart contract trust anchors.
        </p>

        <div style={{ display: "flex", justifyContent: "center", gap: "14px", flexWrap: "wrap" }}>
          <button
            onClick={() => handleRoleLaunch("HOLDER", "/wallet")}
            style={{
              padding: "12px 24px",
              borderRadius: "10px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.95rem",
              border: "none",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              boxShadow: "0 4px 14px rgba(37,99,235,0.4)"
            }}
          >
            Launch Holder Wallet
            <ArrowRight size={18} />
          </button>

          <Link
            to="/docs"
            style={{
              padding: "12px 24px",
              borderRadius: "10px",
              backgroundColor: "#1f2937",
              color: "#e2e8f0",
              fontWeight: 600,
              fontSize: "0.95rem",
              border: "1px solid #374151",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px"
            }}
          >
            <FileCode size={18} />
            View Architecture Docs
          </Link>
        </div>
      </div>

      {/* Role Portals Grid */}
      <div style={{ marginBottom: "64px" }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <span style={{ fontSize: "0.8rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Comprehensive 5-Role Platform
          </span>
          <h2 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#f8fafc", margin: "6px 0 0 0" }}>
            Specialized Portals for Every SSI Stakeholder
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
          {portals.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.role}
                onClick={() => handleRoleLaunch(p.role, p.path)}
                style={{
                  backgroundColor: "#111827",
                  border: "1px solid #1f2937",
                  borderRadius: "16px",
                  padding: "22px",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  transition: "all 0.2s ease"
                }}
                className="portal-card-hover"
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                    <div
                      style={{
                        padding: "10px",
                        borderRadius: "10px",
                        backgroundColor: "rgba(255, 255, 255, 0.05)",
                        border: "1px solid rgba(255, 255, 255, 0.1)"
                      }}
                    >
                      <Icon size={22} color={p.accent} />
                    </div>
                    <span
                      style={{
                        fontSize: "0.68rem",
                        fontWeight: 700,
                        color: "#cbd5e1",
                        backgroundColor: "#161f33",
                        padding: "3px 8px",
                        borderRadius: "6px"
                      }}
                    >
                      {p.badge}
                    </span>
                  </div>

                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: "0 0 4px 0" }}>
                    {p.title}
                  </h3>
                  <div style={{ fontSize: "0.78rem", color: "#60a5fa", fontWeight: 600, marginBottom: "8px" }}>
                    {p.subtitle}
                  </div>
                  <p style={{ fontSize: "0.78rem", color: "#94a3b8", lineHeight: 1.5, margin: 0 }}>
                    {p.desc}
                  </p>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    marginTop: "18px",
                    fontSize: "0.78rem",
                    fontWeight: 700,
                    color: p.accent
                  }}
                >
                  <span>Launch Portal</span>
                  <ArrowRight size={14} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Core Architectural Pillars */}
      <div>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <span style={{ fontSize: "0.8rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Engineering Pillars
          </span>
          <h2 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#f8fafc", margin: "6px 0 0 0" }}>
            Robust, Standards-Aligned SSI Security Stack
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
          {coreFeatures.map((feat, idx) => {
            const Icon = feat.icon;
            return (
              <div
                key={idx}
                style={{
                  backgroundColor: "#0d131f",
                  border: "1px solid #1f2937",
                  borderRadius: "14px",
                  padding: "20px",
                  display: "flex",
                  gap: "16px"
                }}
              >
                <div
                  style={{
                    padding: "10px",
                    borderRadius: "10px",
                    backgroundColor: "rgba(255, 255, 255, 0.04)",
                    height: "fit-content"
                  }}
                >
                  <Icon size={22} color={feat.color} />
                </div>
                <div>
                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc", margin: "0 0 6px 0" }}>
                    {feat.title}
                  </h4>
                  <p style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: 1.5, margin: 0 }}>
                    {feat.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
