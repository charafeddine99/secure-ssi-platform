import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { 
  KeyRound, 
  Building2, 
  Search, 
  Users, 
  Settings, 
  ArrowRight, 
  Sparkles,
  Check,
  Copy
} from "lucide-react";

export const AuthPage: React.FC<{ onComplete?: () => void }> = ({ onComplete }) => {
  const { login, register, loginWithMetaMask, loginWithSeedPhrase, switchDemoRole } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"demo" | "login" | "register" | "seed">("demo");

  // Login form
  const [loginEmail, setLoginEmail] = useState("holder@example.test");
  const [loginPassword, setLoginPassword] = useState("Holder-Prototype-2026!");

  // Register form
  const [regName, setRegName] = useState("Demo Citizen");
  const [regNationalId, setRegNationalId] = useState("DEMO-NAT-829104");
  const [regEmail, setRegEmail] = useState("citizen@example.test");
  const [regOrganization, setRegOrganization] = useState("Demo Identity Framework [DEMO ENVIRONMENT]");
  const [regPassword, setRegPassword] = useState("Prototype-2026!");

  // Seed phrase login
  const [seedPhraseInput, setSeedPhraseInput] = useState("");

  // Revealed new identity after register
  const [newIdentity, setNewIdentity] = useState<{
    did: string;
    seedPhrase: string;
    walletAddress: string;
  } | null>(null);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const demoAccounts = [
    {
      role: "HOLDER" as const,
      title: "Demo Holder (Student / Citizen)",
      email: "holder@example.test",
      password: "Holder-Prototype-2026!",
      org: "Demo Academic Wallet",
      targetPath: "/wallet",
      icon: KeyRound,
      color: "#6366f1",
      badge: "Primary Citizen Role",
      desc: "Access digital wallet, inspect credentials, scan OID4VCI offers, and grant selective disclosure."
    },
    {
      role: "ISSUER" as const,
      title: "Demo University (Issuer Authority)",
      email: "issuer@example.test",
      password: "Issuer-Prototype-2026!",
      org: "Demo University (Accredited Issuer)",
      targetPath: "/issuer",
      icon: Building2,
      color: "#2563eb",
      badge: "Institutional Issuer",
      desc: "Issue Academic Degree credentials, manage W3C Bitstring 1.0 status lists, and revoke credentials."
    },
    {
      role: "VERIFIER" as const,
      title: "Demo Company (Trust Verifier)",
      email: "verifier@example.test",
      password: "Verifier-Prototype-2026!",
      org: "Demo Company Compliance",
      targetPath: "/verifier",
      icon: Search,
      color: "#059669",
      badge: "Relying Party",
      desc: "Create OID4VP verification requests, inspect cryptographic proofs, and verify predicate conditions."
    },
    {
      role: "GUARDIAN" as const,
      title: "Demo Social Recovery Guardian #1",
      email: "admin@example.test",
      password: "Admin-Prototype-2026!",
      org: "Demo Guardian Quorum",
      targetPath: "/guardian",
      icon: Users,
      color: "#d97706",
      badge: "Key Guardian",
      desc: "Review wallet recovery petitions, vote with Shamir key shares, and sign threshold authorizations."
    },
    {
      role: "ADMIN" as const,
      title: "Demo Platform Administrator",
      email: "admin@example.test",
      password: "Admin-Prototype-2026!",
      org: "Secure SSI Platform Ops",
      targetPath: "/admin",
      icon: Settings,
      color: "#7c3aed",
      badge: "System Operations",
      desc: "Live microservices telemetry, Hardhat EVM smart contract logs, and real-time AI fraud monitoring."
    }
  ];

  const handleQuickDemoLaunch = (account: typeof demoAccounts[0]) => {
    switchDemoRole(account.role);
    login(account.email, account.password);
    if (onComplete) onComplete();
    navigate(account.targetPath);
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!loginEmail.trim()) {
      setErrorMsg("Please enter a valid email or DID identifier.");
      return;
    }
    const success = login(loginEmail, loginPassword);
    if (success) {
      if (onComplete) onComplete();
      navigate("/wallet");
    } else {
      setErrorMsg("Authentication failed. Please verify credentials.");
    }
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!regName.trim() || !regEmail.trim()) {
      setErrorMsg("Please fill in Full Name and Email fields.");
      return;
    }
    const res = register(regName, regNationalId, regEmail, regOrganization, regPassword);
    setNewIdentity({
      did: res.user.did,
      seedPhrase: res.seedPhrase,
      walletAddress: res.user.walletAddress
    });
  };

  const handleSeedLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!seedPhraseInput.trim()) {
      setErrorMsg("Please enter your 12 or 24-word recovery seed phrase.");
      return;
    }
    const success = loginWithSeedPhrase(seedPhraseInput);
    if (success) {
      if (onComplete) onComplete();
      navigate("/wallet");
    } else {
      setErrorMsg("Invalid recovery phrase. Please supply valid BIP-39 mnemonic words.");
    }
  };

  const handleMetaMask = async () => {
    setErrorMsg(null);
    const success = await loginWithMetaMask();
    if (success) {
      if (onComplete) onComplete();
      navigate("/wallet");
    } else {
      setErrorMsg("MetaMask connection failed. Please ensure your Web3 wallet extension is unlocked.");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      minHeight: "calc(100vh - 140px)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "32px 16px"
    }}>
      <div style={{
        width: "100%",
        maxWidth: "580px",
        backgroundColor: "#111827",
        border: "1px solid #1f2937",
        borderRadius: "16px",
        padding: "32px",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)"
      }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "4px 12px",
            borderRadius: "9999px",
            backgroundColor: "rgba(245, 158, 11, 0.12)",
            border: "1px solid rgba(245, 158, 11, 0.3)",
            color: "#fbbf24",
            fontSize: "0.75rem",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            marginBottom: "12px"
          }}>
            <Sparkles size={13} />
            DEMO ENVIRONMENT — ACADEMIC EVALUATION
          </div>

          <h1 style={{ fontSize: "1.45rem", fontWeight: 800, color: "#ffffff", marginBottom: "6px", letterSpacing: "-0.02em" }}>
            Identity &amp; Access Gateway
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8", lineHeight: 1.4 }}>
            W3C VC 2.0 • Ed25519 Data Integrity • OID4VCI &amp; OID4VP • EIP-4337
          </p>
        </div>

        {/* Tab switcher */}
        <div style={{
          display: "flex",
          backgroundColor: "#0b0f19",
          padding: "4px",
          borderRadius: "10px",
          marginBottom: "24px",
          border: "1px solid #1f2937"
        }}>
          <button
            type="button"
            onClick={() => { setMode("demo"); setErrorMsg(null); }}
            style={{
              flex: 1,
              padding: "9px 12px",
              fontSize: "12px",
              fontWeight: 700,
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "demo" ? "#2563eb" : "transparent",
              color: mode === "demo" ? "#ffffff" : "#94a3b8",
              transition: "all 0.15s ease"
            }}
          >
            ⚡ Demo Personas
          </button>
          <button
            type="button"
            onClick={() => { setMode("login"); setErrorMsg(null); }}
            style={{
              flex: 1,
              padding: "9px 12px",
              fontSize: "12px",
              fontWeight: 700,
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "login" ? "#2563eb" : "transparent",
              color: mode === "login" ? "#ffffff" : "#94a3b8",
              transition: "all 0.15s ease"
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode("register"); setErrorMsg(null); setNewIdentity(null); }}
            style={{
              flex: 1,
              padding: "9px 12px",
              fontSize: "12px",
              fontWeight: 700,
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "register" ? "#2563eb" : "transparent",
              color: mode === "register" ? "#ffffff" : "#94a3b8",
              transition: "all 0.15s ease"
            }}
          >
            New Identity
          </button>
          <button
            type="button"
            onClick={() => { setMode("seed"); setErrorMsg(null); }}
            style={{
              flex: 1,
              padding: "9px 12px",
              fontSize: "12px",
              fontWeight: 700,
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "seed" ? "#2563eb" : "transparent",
              color: mode === "seed" ? "#ffffff" : "#94a3b8",
              transition: "all 0.15s ease"
            }}
          >
            Seed Phrase
          </button>
        </div>

        {errorMsg && (
          <div style={{
            padding: "12px 14px",
            borderRadius: "8px",
            backgroundColor: "rgba(239, 68, 68, 0.12)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#f87171",
            fontSize: "12px",
            marginBottom: "18px"
          }}>
            {errorMsg}
          </div>
        )}

        {/* 1. DEMO PERSONAS MODE (RECOMMENDED FOR EVALUATORS) */}
        {mode === "demo" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
              Select a documented stakeholder persona for immediate, zero-friction evaluation:
            </div>

            {demoAccounts.map((account) => {
              const IconComp = account.icon;
              return (
                <div
                  key={account.role}
                  onClick={() => handleQuickDemoLaunch(account)}
                  style={{
                    backgroundColor: "#0b0f19",
                    border: `1px solid ${account.color}40`,
                    borderRadius: "12px",
                    padding: "14px 16px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    transition: "all 0.15s ease"
                  }}
                  className="portal-card-hover"
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{
                      width: "36px",
                      height: "36px",
                      borderRadius: "10px",
                      backgroundColor: `${account.color}20`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: account.color
                    }}>
                      <IconComp size={18} />
                    </div>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontWeight: 700, fontSize: "0.9rem", color: "#f8fafc" }}>
                          {account.title}
                        </span>
                        <span style={{
                          fontSize: "0.68rem",
                          fontWeight: 700,
                          backgroundColor: `${account.color}25`,
                          color: account.color,
                          padding: "2px 6px",
                          borderRadius: "4px"
                        }}>
                          {account.badge}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "2px" }}>
                        {account.desc}
                      </div>
                    </div>
                  </div>
                  <ArrowRight size={16} color="#64748b" />
                </div>
              );
            })}
          </div>
        )}

        {/* 2. MANUAL LOGIN MODE */}
        {mode === "login" && (
          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}>
                Username / Email / DID
              </label>
              <input
                type="text"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                placeholder="holder@example.test or did:key:..."
                style={{
                  width: "100%",
                  padding: "11px 14px",
                  borderRadius: "8px",
                  backgroundColor: "#0b0f19",
                  border: "1px solid #1f2937",
                  color: "#f8fafc",
                  fontSize: "13px",
                  outline: "none"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}>
                Password / Secret PIN
              </label>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="••••••••••••"
                style={{
                  width: "100%",
                  padding: "11px 14px",
                  borderRadius: "8px",
                  backgroundColor: "#0b0f19",
                  border: "1px solid #1f2937",
                  color: "#f8fafc",
                  fontSize: "13px",
                  outline: "none"
                }}
              />
            </div>

            <button
              type="submit"
              style={{
                marginTop: "6px",
                padding: "12px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer"
              }}
            >
              Sign In to Identity Wallet
            </button>

            <div style={{ display: "flex", alignItems: "center", gap: "12px", margin: "4px 0" }}>
              <div style={{ flex: 1, height: "1px", backgroundColor: "#1f2937" }} />
              <span style={{ fontSize: "11px", color: "#64748b" }}>OR WEB3</span>
              <div style={{ flex: 1, height: "1px", backgroundColor: "#1f2937" }} />
            </div>

            <button
              type="button"
              onClick={handleMetaMask}
              style={{
                padding: "11px",
                backgroundColor: "#0b0f19",
                color: "#f8fafc",
                border: "1px solid #1f2937",
                borderRadius: "8px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px"
              }}
            >
              🦊 Verify with Web3 Wallet (MetaMask)
            </button>
          </form>
        )}

        {/* 3. NEW IDENTITY GENERATION */}
        {mode === "register" && !newIdentity && (
          <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "4px" }}>
                Full Name
              </label>
              <input
                type="text"
                value={regName}
                onChange={(e) => setRegName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#0b0f19",
                  border: "1px solid #1f2937",
                  color: "#f8fafc",
                  fontSize: "13px"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "4px" }}>
                National / Student ID Reference
              </label>
              <input
                type="text"
                value={regNationalId}
                onChange={(e) => setRegNationalId(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#0b0f19",
                  border: "1px solid #1f2937",
                  color: "#f8fafc",
                  fontSize: "13px"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "4px" }}>
                Email Address
              </label>
              <input
                type="email"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#0b0f19",
                  border: "1px solid #1f2937",
                  color: "#f8fafc",
                  fontSize: "13px"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "4px" }}>
                Organization Affiliation
              </label>
              <input
                type="text"
                value={regOrganization}
                onChange={(e) => setRegOrganization(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#0b0f19",
                  border: "1px solid #1f2937",
                  color: "#f8fafc",
                  fontSize: "13px"
                }}
              />
            </div>

            <button
              type="submit"
              style={{
                marginTop: "8px",
                padding: "11px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer"
              }}
            >
              🔐 Generate Ed25519 DID Key Pair
            </button>
          </form>
        )}

        {/* 3B. NEW IDENTITY CREATED */}
        {mode === "register" && newIdentity && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{
              padding: "12px",
              borderRadius: "8px",
              backgroundColor: "rgba(16, 185, 129, 0.12)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#34d399",
              fontSize: "13px",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "8px"
            }}>
              <Check size={16} />
              Self-Sovereign Identity Generated Successfully
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#94a3b8", marginBottom: "4px" }}>
                W3C Decentralized Identifier (DID)
              </label>
              <div style={{
                padding: "10px",
                backgroundColor: "#0b0f19",
                border: "1px solid #1f2937",
                borderRadius: "8px",
                fontFamily: "var(--font-mono)",
                fontSize: "11px",
                color: "#60a5fa",
                wordBreak: "break-all"
              }}>
                {newIdentity.did}
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#fbbf24", marginBottom: "4px" }}>
                ⚠️ 12-Word Recovery Seed Phrase (Store in a Safe Location)
              </label>
              <div style={{
                padding: "12px",
                backgroundColor: "rgba(245, 158, 11, 0.08)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                borderRadius: "8px",
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                color: "#fcd34d",
                lineHeight: "1.6"
              }}>
                {newIdentity.seedPhrase}
              </div>
            </div>

            <button
              type="button"
              onClick={() => copyToClipboard(newIdentity.seedPhrase)}
              style={{
                padding: "10px",
                backgroundColor: "#0b0f19",
                color: "#f8fafc",
                border: "1px solid #1f2937",
                borderRadius: "8px",
                fontSize: "12px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px"
              }}
            >
              <Copy size={14} />
              {copied ? "✓ Copied to Clipboard!" : "Copy Seed Phrase"}
            </button>

            <button
              type="button"
              onClick={() => { if (onComplete) onComplete(); navigate("/wallet"); }}
              style={{
                padding: "11px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer"
              }}
            >
              Proceed to Wallet
            </button>
          </div>
        )}

        {/* 4. SEED LOGIN */}
        {mode === "seed" && (
          <form onSubmit={handleSeedLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}>
                12 or 24-Word Recovery Seed Phrase
              </label>
              <textarea
                value={seedPhraseInput}
                onChange={(e) => setSeedPhraseInput(e.target.value)}
                placeholder="apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard..."
                rows={4}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  backgroundColor: "#0b0f19",
                  border: "1px solid #1f2937",
                  color: "#f8fafc",
                  fontSize: "12px",
                  fontFamily: "var(--font-mono)",
                  lineHeight: "1.5",
                  resize: "vertical",
                  outline: "none"
                }}
              />
            </div>

            <button
              type="submit"
              style={{
                padding: "11px",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer"
              }}
            >
              Recover Identity &amp; Sign In
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
