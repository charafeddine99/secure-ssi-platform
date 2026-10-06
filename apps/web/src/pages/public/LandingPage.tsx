import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { TrustBadge } from "../../components/common/TrustBadge";
import { 
  ShieldCheck, 
  KeyRound, 
  Lock, 
  Building2, 
  Search, 
  Users, 
  Settings, 
  ArrowRight,
  FileCode,
  QrCode,
  FileCheck,
  Sparkles,
  Globe,
  Fingerprint,
  ChevronRight
} from "lucide-react";

export const LandingPage: React.FC = () => {
  const { switchDemoRole } = useAuth();
  const navigate = useNavigate();

  const handleRoleLaunch = (role: "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN", path: string) => {
    switchDemoRole(role);
    navigate(path);
  };

  const coreBenefits = [
    {
      title: "User-Controlled Identity",
      tagline: "Sovereign Custody",
      description: "Cryptographic ownership powered by W3C DID Core (did:key & did:web). Private keys are held in sovereign custody—never exposed to centralized identity providers.",
      icon: KeyRound,
      color: "#60a5fa"
    },
    {
      title: "Privacy-Preserving Credentials",
      tagline: "Holder Consent & Minimization",
      description: "Holders control presentation authorization and credential selection. Verified via Data Integrity eddsa-jcs-2022 proofs with tamper-evident issuer credential preservation.",
      icon: Lock,
      color: "#34d399"
    },
    {
      title: "Trusted Instant Verification",
      tagline: "Sub-Millisecond Proofs",
      description: "W3C VC 2.0 credentials canonicalized via RFC 8785 (JCS) and signed with Ed25519. Validated through our comprehensive 9-point verification matrix.",
      icon: FileCheck,
      color: "#c084fc"
    },
    {
      title: "Decentralized Security & Recovery",
      tagline: "EVM Anchored & M-of-N Quorum",
      description: "Zero-PII blockchain anchoring on Ethereum testnets paired with 3-of-5 Shamir Secret Sharing social recovery for seedless, non-custodial wallet restoration.",
      icon: ShieldCheck,
      color: "#fbbf24"
    }
  ];

  const workflowSteps = [
    {
      step: "01",
      actor: "Sovereign User",
      title: "Wallet Creation",
      desc: "Generates Ed25519 keypair and sovereign did:key identifier. No central account required.",
      icon: Fingerprint,
      accent: "#3b82f6"
    },
    {
      step: "02",
      actor: "Accredited Issuer",
      title: "Credential Issuance",
      desc: "University or institution signs W3C VC 2.0 with eddsa-jcs-2022 and reserves bitstring status index.",
      icon: Building2,
      accent: "#2563eb"
    },
    {
      step: "03",
      actor: "Sovereign Wallet",
      title: "OID4VCI Claim",
      desc: "Wallet scans QR offer, exchanges pre-authorized code, and securely stores the signed credential.",
      icon: QrCode,
      accent: "#10b981"
    },
    {
      step: "04",
      actor: "Relying Party",
      title: "OID4VP Verification",
      desc: "Verifier requests claims; holder authorizes credential selection; 9-point trust matrix audits proof in ~0.3 ms.",
      icon: Search,
      accent: "#8b5cf6"
    }
  ];

  const portals = [
    {
      role: "HOLDER" as const,
      title: "Holder Wallet",
      subtitle: "Personal Sovereign Identity & Credential Vault",
      desc: "Tactile digital credential cards, QR presentation, and granular holder presentation consent.",
      icon: ShieldCheck,
      path: "/wallet",
      accent: "#2563eb",
      badge: "Sovereign User"
    },
    {
      role: "ISSUER" as const,
      title: "Issuer Console",
      subtitle: "Institutional Credential Issuance & Status",
      desc: "Issue W3C VC 2.0 credentials with pre-issuance AI threat evaluation and on-chain bitstring anchoring.",
      icon: Building2,
      path: "/issuer",
      accent: "#1d4ed8",
      badge: "Accredited Authority"
    },
    {
      role: "VERIFIER" as const,
      title: "Verifier Service",
      subtitle: "Presentation Request & Cryptographic Audit",
      desc: "Validate Ed25519 signatures, revocation bitstrings, and DCQL requested claims in sub-millisecond speeds.",
      icon: Search,
      path: "/verifier",
      accent: "#059669",
      badge: "Relying Party"
    },
    {
      role: "GUARDIAN" as const,
      title: "Guardian Recovery",
      subtitle: "3-of-5 Multi-Sig Social Recovery",
      desc: "Participate in Shamir secret quorum signing to securely rotate keys for compromised or lost wallets.",
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
      badge: "Platform Ops"
    }
  ];

  const goldenPathSteps: Array<{
    step: number;
    title: string;
    role: "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN";
    path: string;
    desc: string;
  }> = [
    { step: 1, title: "Issuer Creates Credential Schema", role: "ISSUER", path: "/issuer/templates", desc: "Define W3C VC 2.0 schema, claim definitions, and status list bit assignment." },
    { step: 2, title: "Issuer Issues Credential", role: "ISSUER", path: "/issuer/issue", desc: "Generate Ed25519 Data Integrity proof, sign credential, and produce OID4VCI offer." },
    { step: 3, title: "Holder Receives Credential", role: "HOLDER", path: "/wallet/scan", desc: "Scan or ingest OID4VCI credential offer via deep-link protocol trigger." },
    { step: 4, title: "Credential Appears in Wallet", role: "HOLDER", path: "/wallet", desc: "Inspect newly anchored credential card, claims, and cryptographic proof." },
    { step: 5, title: "Verifier Creates Verification Request", role: "VERIFIER", path: "/verifier/request", desc: "Generate OID4VP presentation definition with challenge nonce and required claims." },
    { step: 6, title: "Holder Approves Sharing", role: "HOLDER", path: "/wallet/consent", desc: "Review request purpose, authorize credential selection, and sign holder presentation proof." },
    { step: 7, title: "Verifier Receives Verification Result", role: "VERIFIER", path: "/verifier/verify", desc: "9-point trust audit confirms signature, validity, non-revocation, and zero-leakage." },
    { step: 8, title: "Audit Log Records Event", role: "ADMIN", path: "/admin/audit", desc: "Inspect append-only tamper-proof audit trail and Hardhat EVM anchored event." }
  ];

  const techStack = [
    { name: "W3C VC DM 2.0", category: "Standard", desc: "Verifiable Credentials Data Model v2.0 with JSON-LD context" },
    { name: "RFC 8785 JCS", category: "Canonicalization", desc: "Deterministic JSON canonicalization scheme" },
    { name: "eddsa-jcs-2022", category: "Cryptosuite", desc: "Ed25519 Data Integrity proofs with multibase z-encodings" },
    { name: "OID4VCI & OID4VP", category: "Protocols", desc: "OpenID for Verifiable Credential Issuance & Presentations" },
    { name: "Bitstring Status List", category: "Revocation", desc: "W3C Bitstring 1.0 (131,072 entries, GZIP compressed, LRU cached)" },
    { name: "EVM Smart Contracts", category: "Anchoring", desc: "Solidity 0.8.28 (DIDRegistry, RevocationRegistry, EmergencyRecovery)" },
    { name: "Hybrid AI Engine", category: "Defense", desc: "Dual-model threat detection (XGBoost + Autoencoder, F1=0.943)" },
    { name: "FastAPI & MongoDB", category: "Backend", desc: "4 independent microservices + authoritative compound indexed DB" },
    { name: "React 18 & Vite 6", category: "Frontend", desc: "TypeScript client cockpit with 5 specialized stakeholder portals" }
  ];

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "48px 24px" }}>
      {/* 1. HERO SECTION */}
      <section style={{ textAlign: "center", marginBottom: "68px" }}>
        <div style={{ display: "inline-flex", gap: "8px", alignItems: "center", marginBottom: "18px", flexWrap: "wrap", justifyContent: "center" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="BLOCKCHAIN_ANCHORED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>

        <h1
          style={{
            fontSize: "clamp(2.3rem, 5vw, 3.6rem)",
            fontWeight: 800,
            letterSpacing: "-0.03em",
            color: "#ffffff",
            lineHeight: 1.15,
            maxWidth: "960px",
            margin: "0 auto 22px auto"
          }}
        >
          Secure Self-Sovereign Identity <br />
          <span style={{ background: "linear-gradient(135deg, #60a5fa 0%, #3b82f6 50%, #93c5fd 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Academic Platform Reference Implementation
          </span>
        </h1>

        <p
          style={{
            fontSize: "1.12rem",
            color: "#94a3b8",
            maxWidth: "820px",
            margin: "0 auto 36px auto",
            lineHeight: 1.65
          }}
        >
          A state-of-the-art decentralized identity system integrating <strong>W3C Verifiable Credentials 2.0</strong>, 
          <strong>OpenID for Verifiable Credentials (OID4VCI / OID4VP)</strong>, 
          advisory <strong>Hybrid AI threat evaluation</strong>, 
          and zero-PII <strong>Ethereum smart contract trust anchors</strong>.
        </p>

        <div style={{ display: "flex", justifyContent: "center", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
          <button
            onClick={() => handleRoleLaunch("HOLDER", "/wallet")}
            style={{
              padding: "12px 22px",
              borderRadius: "10px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.92rem",
              border: "none",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              boxShadow: "0 4px 16px rgba(37,99,235,0.4)"
            }}
          >
            Start as Holder
            <ArrowRight size={17} />
          </button>

          <button
            onClick={() => handleRoleLaunch("ISSUER", "/issuer")}
            style={{
              padding: "12px 20px",
              borderRadius: "10px",
              backgroundColor: "#111827",
              border: "1px solid #1f2937",
              color: "#e2e8f0",
              fontWeight: 600,
              fontSize: "0.92rem",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px"
            }}
          >
            <Building2 size={17} color="#60a5fa" />
            Start as Issuer
          </button>

          <button
            onClick={() => handleRoleLaunch("VERIFIER", "/verifier")}
            style={{
              padding: "12px 20px",
              borderRadius: "10px",
              backgroundColor: "#111827",
              border: "1px solid #1f2937",
              color: "#e2e8f0",
              fontWeight: 600,
              fontSize: "0.92rem",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px"
            }}
          >
            <Search size={17} color="#34d399" />
            Start as Verifier
          </button>

          <button
            onClick={() => handleRoleLaunch("ADMIN", "/admin")}
            style={{
              padding: "12px 20px",
              borderRadius: "10px",
              backgroundColor: "#111827",
              border: "1px solid #1f2937",
              color: "#e2e8f0",
              fontWeight: 600,
              fontSize: "0.92rem",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px"
            }}
          >
            <Settings size={17} color="#a78bfa" />
            Start Admin View
          </button>

          <Link
            to="/docs"
            style={{
              padding: "12px 18px",
              borderRadius: "10px",
              backgroundColor: "#1f2937",
              color: "#94a3b8",
              fontWeight: 600,
              fontSize: "0.9rem",
              border: "1px solid #374151",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            <FileCode size={16} />
            Docs &amp; Specs
          </Link>
        </div>
      </section>

      {/* 2. WHAT IS SSI & WHY THIS PLATFORM EXISTS */}
      <section style={{ marginBottom: "72px" }}>
        <div style={{ textAlign: "center", marginBottom: "36px" }}>
          <span style={{ fontSize: "0.8rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Conceptual Foundation
          </span>
          <h2 style={{ fontSize: "1.9rem", fontWeight: 800, color: "#f8fafc", margin: "6px 0 0 0" }}>
            The Paradigm Shift to Self-Sovereign Identity
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
          {/* Centralized Comparison Card */}
          <div
            style={{
              backgroundColor: "#0d131f",
              borderRadius: "16px",
              border: "1px solid #1f2937",
              padding: "26px"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
              <div style={{ padding: "8px", borderRadius: "8px", backgroundColor: "rgba(239, 68, 68, 0.1)", color: "#f87171" }}>
                <Globe size={22} />
              </div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#f87171", margin: 0 }}>
                Legacy Centralized & Federated Identity (Web2)
              </h3>
            </div>
            <p style={{ fontSize: "0.85rem", color: "#94a3b8", lineHeight: 1.6, margin: "0 0 16px 0" }}>
              Traditional identity relies on centralized silos (passwords, social logins, identity providers). 
              Intermediaries track every login, control account access, and present massive single-point-of-failure honeypots.
            </p>
            <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "0.82rem", color: "#cbd5e1", lineHeight: 1.7 }}>
              <li>User credentials are locked in third-party databases.</li>
              <li>Identity providers track user activity across relying parties.</li>
              <li>Breaches expose unencrypted PII across thousands of accounts.</li>
            </ul>
          </div>

          {/* Self-Sovereign Card */}
          <div
            style={{
              backgroundColor: "#0b162c",
              borderRadius: "16px",
              border: "1px solid #1d4ed8",
              padding: "26px"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
              <div style={{ padding: "8px", borderRadius: "8px", backgroundColor: "rgba(37, 99, 235, 0.2)", color: "#60a5fa" }}>
                <KeyRound size={22} />
              </div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#60a5fa", margin: 0 }}>
                Self-Sovereign Identity (SSI & W3C Standards)
              </h3>
            </div>
            <p style={{ fontSize: "0.85rem", color: "#cbd5e1", lineHeight: 1.6, margin: "0 0 16px 0" }}>
              Users own and control their digital credentials in a sovereign digital wallet. 
              Cryptographic linked data proofs (Ed25519) verify authenticity mathematically without phoning home to issuers.
            </p>
            <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "0.82rem", color: "#e2e8f0", lineHeight: 1.7 }}>
              <li>Private keys remain strictly in sovereign holder custody.</li>
              <li>Holder consent determines credential presentation and claim minimization authorization.</li>
              <li>Decentralized trust anchors (smart contracts) guarantee tamper-evident status tracking with zero PII.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* 3. FOUR CORE BENEFITS */}
      <section style={{ marginBottom: "72px" }}>
        <div style={{ textAlign: "center", marginBottom: "36px" }}>
          <span style={{ fontSize: "0.8rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Platform Benefits
          </span>
          <h2 style={{ fontSize: "1.9rem", fontWeight: 800, color: "#f8fafc", margin: "6px 0 0 0" }}>
            Architectural Guarantees Built Into Every Layer
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "18px" }}>
          {coreBenefits.map((b, i) => {
            const Icon = b.icon;
            return (
              <div
                key={i}
                style={{
                  backgroundColor: "#111827",
                  border: "1px solid #1f2937",
                  borderRadius: "16px",
                  padding: "24px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                    <div style={{ padding: "10px", borderRadius: "10px", backgroundColor: "rgba(255, 255, 255, 0.05)" }}>
                      <Icon size={24} color={b.color} />
                    </div>
                    <span style={{ fontSize: "0.7rem", fontWeight: 700, color: b.color, backgroundColor: "rgba(255,255,255,0.04)", padding: "3px 8px", borderRadius: "6px" }}>
                      {b.tagline}
                    </span>
                  </div>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff", margin: "0 0 8px 0" }}>
                    {b.title}
                  </h3>
                  <p style={{ fontSize: "0.82rem", color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>
                    {b.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. HOW IT WORKS (USER -> ISSUER -> WALLET -> VERIFIER) */}
      <section style={{ marginBottom: "72px" }}>
        <div style={{ textAlign: "center", marginBottom: "36px" }}>
          <span style={{ fontSize: "0.8rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Protocol Lifecycle
          </span>
          <h2 style={{ fontSize: "1.9rem", fontWeight: 800, color: "#f8fafc", margin: "6px 0 0 0" }}>
            How It Works: End-to-End SSI Trust Triangle
          </h2>
          <p style={{ fontSize: "0.9rem", color: "#94a3b8", maxWidth: "680px", margin: "8px auto 0 auto" }}>
            Standards-aligned credential lifecycle powered by OpenID for Verifiable Credential Issuance (OID4VCI) and Presentations (OID4VP).
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
          {workflowSteps.map((w, i) => {
            const Icon = w.icon;
            return (
              <div
                key={i}
                style={{
                  backgroundColor: "#0d131f",
                  border: "1px solid #1f2937",
                  borderRadius: "16px",
                  padding: "24px",
                  position: "relative"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div style={{ padding: "10px", borderRadius: "10px", backgroundColor: "rgba(255, 255, 255, 0.05)" }}>
                    <Icon size={22} color={w.accent} />
                  </div>
                  <span style={{ fontSize: "1.2rem", fontWeight: 900, color: "#374151", fontFamily: "var(--font-mono)" }}>
                    {w.step}
                  </span>
                </div>
                <div style={{ fontSize: "0.72rem", color: w.accent, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px" }}>
                  {w.actor}
                </div>
                <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#f8fafc", margin: "0 0 8px 0" }}>
                  {w.title}
                </h3>
                <p style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: 1.5, margin: 0 }}>
                  {w.desc}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* 5. 5-ROLE SPECIALIZED PORTALS */}
      <section style={{ marginBottom: "72px" }}>
        <div style={{ textAlign: "center", marginBottom: "36px" }}>
          <span style={{ fontSize: "0.8rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Comprehensive Architecture
          </span>
          <h2 style={{ fontSize: "1.9rem", fontWeight: 800, color: "#f8fafc", margin: "6px 0 0 0" }}>
            5 Specialized Stakeholder Portals
          </h2>
          <p style={{ fontSize: "0.9rem", color: "#94a3b8", maxWidth: "680px", margin: "8px auto 0 auto" }}>
            Every role in the ecosystem has a tailored cockpit designed for their operational responsibilities.
          </p>
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
      </section>

      {/* 6. GRADUATION DEFENSE DEMO SCENARIO WALKTHROUGH */}
      <section style={{ marginBottom: "72px" }}>
        <div
          style={{
            backgroundColor: "#0d131f",
            border: "1px solid #1f2937",
            borderRadius: "20px",
            padding: "32px"
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "24px" }}>
            <div>
              <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", color: "#fbbf24", fontSize: "0.75rem", fontWeight: 700, marginBottom: "6px" }}>
                <Sparkles size={16} />
                <span>RECOMMENDED EVALUATION SCENARIO</span>
              </div>
              <h2 style={{ fontSize: "1.6rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
                Graduation Defense 8-Step Golden Journey
              </h2>
              <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
                Follow this sequential demonstration flow to evaluate the complete end-to-end platform capabilities.
              </p>
            </div>

            <button
              onClick={() => handleRoleLaunch("HOLDER", "/wallet")}
              style={{
                padding: "10px 18px",
                borderRadius: "8px",
                backgroundColor: "#2563eb",
                border: "none",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "0.85rem",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px"
              }}
            >
              Start Step 1
              <ChevronRight size={16} />
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "14px" }}>
            {goldenPathSteps.map((s) => (
              <div
                key={s.step}
                onClick={() => handleRoleLaunch(s.role, s.path)}
                style={{
                  backgroundColor: "#111827",
                  border: "1px solid #1f2937",
                  borderRadius: "12px",
                  padding: "16px",
                  cursor: "pointer",
                  display: "flex",
                  gap: "12px",
                  transition: "all 0.15s ease"
                }}
                className="portal-card-hover"
              >
                <div
                  style={{
                    width: "28px",
                    height: "28px",
                    borderRadius: "50%",
                    backgroundColor: "#1e293b",
                    color: "#60a5fa",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.8rem",
                    fontWeight: 800,
                    flexShrink: 0
                  }}
                >
                  {s.step}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc" }}>
                      {s.title}
                    </span>
                    <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "#94a3b8", backgroundColor: "rgba(255,255,255,0.05)", padding: "2px 6px", borderRadius: "4px" }}>
                      {s.role}
                    </span>
                  </div>
                  <p style={{ fontSize: "0.75rem", color: "#94a3b8", lineHeight: 1.45, margin: 0 }}>
                    {s.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 7. TECHNOLOGY STACK & STANDARDS */}
      <section>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <span style={{ fontSize: "0.8rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Standards & Architecture
          </span>
          <h2 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#f8fafc", margin: "6px 0 0 0" }}>
            Certified Open Standards & Modern Stack
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
          {techStack.map((tech, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: "#111827",
                border: "1px solid #1f2937",
                borderRadius: "12px",
                padding: "18px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff" }}>
                  {tech.name}
                </span>
                <span style={{ fontSize: "0.68rem", fontWeight: 700, color: "#60a5fa", backgroundColor: "#161f33", padding: "2px 6px", borderRadius: "4px" }}>
                  {tech.category}
                </span>
              </div>
              <p style={{ fontSize: "0.78rem", color: "#94a3b8", lineHeight: 1.45, margin: 0 }}>
                {tech.desc}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
