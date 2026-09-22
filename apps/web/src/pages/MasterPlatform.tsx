import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useWallet } from "../context/WalletContext";
import { AuthPage } from "../components/auth/AuthPage";
import { HolderPortal, HolderScreen } from "../components/portals/HolderPortal";
import { IssuerPortal, IssuerScreen } from "../components/portals/IssuerPortal";
import { VerifierPortal, VerifierScreen } from "../components/portals/VerifierPortal";
import { GuardianPortal, GuardianScreen } from "../components/portals/GuardianPortal";
import { AdminPortal, AdminScreen } from "../components/portals/AdminPortal";

export type RoleKey = "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN";

export const MasterPlatform: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const { account, connectWallet } = useWallet();

  // Active Role and screen state
  const [activeRole, setActiveRole] = useState<RoleKey>("HOLDER");
  const [holderScreen, setHolderScreen] = useState<HolderScreen>("DASHBOARD");
  const [issuerScreen, setIssuerScreen] = useState<IssuerScreen>("DASHBOARD");
  const [verifierScreen, setVerifierScreen] = useState<VerifierScreen>("DASHBOARD");
  const [guardianScreen, setGuardianScreen] = useState<GuardianScreen>("REQUESTS");
  const [adminScreen, setAdminScreen] = useState<AdminScreen>("SYSTEM");

  const [showAuthGate, setShowAuthGate] = useState<boolean>(!isAuthenticated);

  // If user unauthenticates or toggles auth
  if (!isAuthenticated && showAuthGate) {
    return <AuthPage onComplete={() => setShowAuthGate(false)} />;
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", backgroundColor: "var(--bg-app)" }}>
      {/* 1. TOP ENTERPRISE HEADER */}
      <header className="enterprise-header">
        <div className="brand-section">
          <div className="brand-logo-badge">SSI</div>
          <div className="brand-titles">
            <div className="brand-main-title">
              SECURE SSI PLATFORM
              <span className="brand-tag">EUDI & W3C VC 2.0</span>
            </div>
            <div className="brand-sub-title">
              OpenID for Verifiable Credential Issuance & Presentations (OID4VCI / OID4VP 1.0)
            </div>
          </div>
        </div>

        {/* Canonical Role Switcher (Section 2 & 12) */}
        <div className="role-bar">
          <button
            onClick={() => setActiveRole("HOLDER")}
            className={`role-btn ${activeRole === "HOLDER" ? "active" : ""}`}
          >
            🪪 Holder (Cüzdan)
          </button>
          <button
            onClick={() => setActiveRole("ISSUER")}
            className={`role-btn ${activeRole === "ISSUER" ? "active" : ""}`}
          >
            🏛️ Issuer (İhraççı)
          </button>
          <button
            onClick={() => setActiveRole("VERIFIER")}
            className={`role-btn ${activeRole === "VERIFIER" ? "active" : ""}`}
          >
            🔍 Verifier (Doğrulayıcı)
          </button>
          <button
            onClick={() => setActiveRole("GUARDIAN")}
            className={`role-btn ${activeRole === "GUARDIAN" ? "active" : ""}`}
          >
            🛡️ Guardian (Vasi)
          </button>
          <button
            onClick={() => setActiveRole("ADMIN")}
            className={`role-btn ${activeRole === "ADMIN" ? "active" : ""}`}
          >
            ⚙️ Admin (Yönetim)
          </button>
        </div>

        {/* Header Right Status Badges */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "11px",
            fontWeight: "700",
            padding: "4px 10px",
            borderRadius: "4px",
            backgroundColor: "rgba(22, 163, 74, 0.12)",
            border: "1px solid rgba(22, 163, 74, 0.3)",
            color: "#4ade80"
          }}>
            <span style={{ fontSize: "8px" }}>●</span> GATEWAY: ONLINE
          </div>

          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            fontSize: "11px"
          }}>
            <span style={{ fontWeight: "700", color: "var(--text-main)" }}>{user?.name || "Sovereign User"}</span>
            <span style={{ color: "#60a5fa", fontFamily: "var(--font-mono)" }}>
              {user?.did ? `${user.did.slice(0, 16)}...` : "did:key:z6Mku..."}
            </span>
          </div>

          <button
            onClick={logout}
            style={{
              padding: "6px 10px",
              backgroundColor: "var(--bg-subtle)",
              color: "var(--text-muted)",
              border: "1px solid var(--border-default)",
              borderRadius: "6px",
              fontSize: "11px",
              cursor: "pointer"
            }}
          >
            Çıkış
          </button>
        </div>
      </header>

      {/* 2. BODY LAYOUT: SIDEBAR + MAIN CONTENT */}
      <div style={{ display: "flex", flex: 1 }}>
        {/* SIDEBAR (SECTION 12 SUB-SCREENS) */}
        <aside style={{
          width: "240px",
          backgroundColor: "var(--bg-surface)",
          borderRight: "1px solid var(--border-default)",
          padding: "20px 12px",
          display: "flex",
          flexDirection: "column",
          gap: "4px"
        }}>
          <div style={{
            fontSize: "11px",
            fontWeight: "700",
            color: "var(--text-tertiary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            padding: "0 10px 10px 10px",
            borderBottom: "1px solid var(--border-default)",
            marginBottom: "6px"
          }}>
            {activeRole} EKRANLARI (BÖLÜM 12)
          </div>

          {/* 1. HOLDER SUB-SCREENS (11 EKRAN) */}
          {activeRole === "HOLDER" && (
            <>
              {[
                { key: "DASHBOARD", label: "📊 Dashboard" },
                { key: "IDENTITY", label: "🪪 Identity (DID)" },
                { key: "WALLET", label: "💼 Wallet (Keys)" },
                { key: "CREDENTIALS", label: "📜 Credentials" },
                { key: "CREDENTIAL_DETAIL", label: "🔍 Credential Detail" },
                { key: "PRESENT", label: "📤 Present (OID4VP)" },
                { key: "CONSENT", label: "🛡️ Consent & ZKP" },
                { key: "VERIFICATION_RESULT", label: "📋 Result Receipt" },
                { key: "ACTIVITY", label: "🕒 Activity Ledger" },
                { key: "SECURITY", label: "🔐 Security & AI" },
                { key: "RECOVERY", label: "🆘 Recovery Setup" }
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => setHolderScreen(item.key as HolderScreen)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: "600",
                    textAlign: "left",
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: holderScreen === item.key ? "var(--color-primary)" : "transparent",
                    color: holderScreen === item.key ? "#ffffff" : "var(--text-muted)",
                    transition: "all 0.15s ease"
                  }}
                >
                  {item.label}
                </button>
              ))}
            </>
          )}

          {/* 2. ISSUER SUB-SCREENS (6 EKRAN) */}
          {activeRole === "ISSUER" && (
            <>
              {[
                { key: "DASHBOARD", label: "📊 Dashboard" },
                { key: "TEMPLATES", label: "📑 Credential Templates" },
                { key: "ISSUE", label: "✍️ Issue Credential" },
                { key: "ISSUED", label: "🗂️ Issued Credentials" },
                { key: "REVOCATION", label: "🚫 Revocation (Bitstring)" },
                { key: "ORGANIZATION", label: "🏢 Organization Profile" }
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => setIssuerScreen(item.key as IssuerScreen)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: "600",
                    textAlign: "left",
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: issuerScreen === item.key ? "var(--color-primary)" : "transparent",
                    color: issuerScreen === item.key ? "#ffffff" : "var(--text-muted)",
                    transition: "all 0.15s ease"
                  }}
                >
                  {item.label}
                </button>
              ))}
            </>
          )}

          {/* 3. VERIFIER SUB-SCREENS (6 EKRAN) */}
          {activeRole === "VERIFIER" && (
            <>
              {[
                { key: "DASHBOARD", label: "📊 Dashboard" },
                { key: "CREATE_REQUEST", label: "📝 Create Request" },
                { key: "QR_LINK", label: "📲 QR / Request Link" },
                { key: "PRESENTATION", label: "📥 Presentation VP" },
                { key: "VERIFICATION_RESULT", label: "✅ Verification Result" },
                { key: "HISTORY", label: "🕒 History Ledger" }
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => setVerifierScreen(item.key as VerifierScreen)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: "600",
                    textAlign: "left",
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: verifierScreen === item.key ? "var(--color-primary)" : "transparent",
                    color: verifierScreen === item.key ? "#ffffff" : "var(--text-muted)",
                    transition: "all 0.15s ease"
                  }}
                >
                  {item.label}
                </button>
              ))}
            </>
          )}

          {/* 4. GUARDIAN SUB-SCREENS (4 EKRAN) */}
          {activeRole === "GUARDIAN" && (
            <>
              {[
                { key: "REQUESTS", label: "📨 Recovery Requests" },
                { key: "REQUEST_DETAIL", label: "🔎 Request Detail" },
                { key: "APPROVE_REJECT", label: "✍️ Approve / Reject" },
                { key: "HISTORY", label: "🕒 History Ledger" }
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => setGuardianScreen(item.key as GuardianScreen)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: "600",
                    textAlign: "left",
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: guardianScreen === item.key ? "var(--color-primary)" : "transparent",
                    color: guardianScreen === item.key ? "#ffffff" : "var(--text-muted)",
                    transition: "all 0.15s ease"
                  }}
                >
                  {item.label}
                </button>
              ))}
            </>
          )}

          {/* 5. ADMIN SUB-SCREENS (8 EKRAN) */}
          {activeRole === "ADMIN" && (
            <>
              {[
                { key: "USERS", label: "👥 Users" },
                { key: "ORGANIZATIONS", label: "🏢 Organizations" },
                { key: "TRUST", label: "🤝 Trust Framework" },
                { key: "FRAUD", label: "🧠 Fraud & AI Rules" },
                { key: "RECOVERY", label: "🛡️ Recovery Policies" },
                { key: "BLOCKCHAIN", label: "⛓️ Blockchain Explorer" },
                { key: "AUDIT", label: "📜 Audit Ledger" },
                { key: "SYSTEM", label: "⚙️ System Telemetry" }
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => setAdminScreen(item.key as AdminScreen)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: "600",
                    textAlign: "left",
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: adminScreen === item.key ? "var(--color-primary)" : "transparent",
                    color: adminScreen === item.key ? "#ffffff" : "var(--text-muted)",
                    transition: "all 0.15s ease"
                  }}
                >
                  {item.label}
                </button>
              ))}
            </>
          )}
        </aside>

        {/* MAIN VIEWPORT */}
        <main style={{ flex: 1, padding: "24px", overflowY: "auto" }}>
          {activeRole === "HOLDER" && (
            <HolderPortal
              activeScreen={holderScreen}
              onNavigate={(s) => setHolderScreen(s)}
            />
          )}

          {activeRole === "ISSUER" && (
            <IssuerPortal
              activeScreen={issuerScreen}
              onNavigate={(s) => setIssuerScreen(s)}
            />
          )}

          {activeRole === "VERIFIER" && (
            <VerifierPortal
              activeScreen={verifierScreen}
              onNavigate={(s) => setVerifierScreen(s)}
            />
          )}

          {activeRole === "GUARDIAN" && (
            <GuardianPortal
              activeScreen={guardianScreen}
              onNavigate={(s) => setGuardianScreen(s)}
            />
          )}

          {activeRole === "ADMIN" && (
            <AdminPortal
              activeScreen={adminScreen}
              onNavigate={(s) => setAdminScreen(s)}
            />
          )}
        </main>
      </div>
    </div>
  );
};
