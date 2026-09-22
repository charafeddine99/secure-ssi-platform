import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";

export const AuthPage: React.FC<{ onComplete?: () => void }> = ({ onComplete }) => {
  const { login, register, loginWithMetaMask, loginWithSeedPhrase, quickDemoLogin } = useAuth();
  const [mode, setMode] = useState<"login" | "register" | "seed">("login");

  // Login form
  const [loginEmail, setLoginEmail] = useState("charaf.bessanane@identity-eudi.eu");
  const [loginPassword, setLoginPassword] = useState("123456");

  // Register form
  const [regName, setRegName] = useState("Charaf Eddine Bessanane");
  const [regNationalId, setRegNationalId] = useState("EU-ID-829104752");
  const [regEmail, setRegEmail] = useState("charaf.bessanane@identity-eudi.eu");
  const [regOrganization, setRegOrganization] = useState("European Digital Identity Framework");
  const [regPassword, setRegPassword] = useState("123456");

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

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!loginEmail.trim()) {
      setErrorMsg("Lütfen geçerli bir e-posta veya DID girin.");
      return;
    }
    login(loginEmail, loginPassword);
    if (onComplete) onComplete();
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!regName.trim() || !regEmail.trim()) {
      setErrorMsg("Lütfen Ad Soyad ve E-posta alanlarını doldurunuz.");
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
      setErrorMsg("Lütfen 12 veya 24 kelimelik kurtarma tohum ifadenizi girin.");
      return;
    }
    const success = loginWithSeedPhrase(seedPhraseInput);
    if (success) {
      if (onComplete) onComplete();
    } else {
      setErrorMsg("Geçersiz kurtarma ifadesi. Lütfen en az 12 geçerli BIP-39 kelimesi girin.");
    }
  };

  const handleMetaMask = async () => {
    setErrorMsg(null);
    const success = await loginWithMetaMask();
    if (success) {
      if (onComplete) onComplete();
    } else {
      setErrorMsg("MetaMask bağlantısı kurulamadı. Lütfen cüzdan eklentinizi kontrol edin.");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "var(--bg-app)",
      padding: "24px"
    }}>
      <div style={{
        width: "100%",
        maxWidth: "480px",
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border-default)",
        borderRadius: "12px",
        padding: "32px",
        boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)"
      }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "48px",
            height: "48px",
            borderRadius: "10px",
            backgroundColor: "var(--color-primary)",
            color: "#ffffff",
            fontWeight: "800",
            fontSize: "20px",
            marginBottom: "12px"
          }}>
            SSI
          </div>
          <h1 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)", marginBottom: "6px" }}>
            Secure SSI Platform
          </h1>
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            EUDI Wallet ARF & W3C Verifiable Credentials 2.0
          </p>
        </div>

        {/* Tab switcher */}
        <div style={{
          display: "flex",
          backgroundColor: "var(--bg-subtle)",
          padding: "4px",
          borderRadius: "8px",
          marginBottom: "24px",
          border: "1px solid var(--border-default)"
        }}>
          <button
            type="button"
            onClick={() => { setMode("login"); setErrorMsg(null); setNewIdentity(null); }}
            style={{
              flex: 1,
              padding: "8px 12px",
              fontSize: "12px",
              fontWeight: "600",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "login" ? "var(--color-primary)" : "transparent",
              color: mode === "login" ? "#ffffff" : "var(--text-muted)",
              transition: "all 0.15s ease"
            }}
          >
            Giriş Yap
          </button>
          <button
            type="button"
            onClick={() => { setMode("register"); setErrorMsg(null); setNewIdentity(null); }}
            style={{
              flex: 1,
              padding: "8px 12px",
              fontSize: "12px",
              fontWeight: "600",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "register" ? "var(--color-primary)" : "transparent",
              color: mode === "register" ? "#ffffff" : "var(--text-muted)",
              transition: "all 0.15s ease"
            }}
          >
            Yeni Kimlik
          </button>
          <button
            type="button"
            onClick={() => { setMode("seed"); setErrorMsg(null); setNewIdentity(null); }}
            style={{
              flex: 1,
              padding: "8px 12px",
              fontSize: "12px",
              fontWeight: "600",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              backgroundColor: mode === "seed" ? "var(--color-primary)" : "transparent",
              color: mode === "seed" ? "#ffffff" : "var(--text-muted)",
              transition: "all 0.15s ease"
            }}
          >
            Kurtarma İfadesi
          </button>
        </div>

        {errorMsg && (
          <div style={{
            padding: "10px 14px",
            borderRadius: "6px",
            backgroundColor: "rgba(220, 38, 38, 0.12)",
            border: "1px solid rgba(220, 38, 38, 0.3)",
            color: "#ef4444",
            fontSize: "12px",
            marginBottom: "16px"
          }}>
            {errorMsg}
          </div>
        )}

        {/* 1. LOGIN MODE */}
        {mode === "login" && (
          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                Kurumsal E-Posta veya DID
              </label>
              <input
                type="text"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                placeholder="ornek@identity-eudi.eu veya did:key:..."
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "13px",
                  outline: "none"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                Parola / PIN
              </label>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="••••••"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "13px",
                  outline: "none"
                }}
              />
            </div>

            <button
              type="submit"
              style={{
                marginTop: "8px",
                padding: "10px",
                backgroundColor: "var(--color-primary)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Kimlik Cüzdanına Giriş Yap
            </button>

            <div style={{ display: "flex", alignItems: "center", gap: "12px", margin: "8px 0" }}>
              <div style={{ flex: 1, height: "1px", backgroundColor: "var(--border-default)" }} />
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>VEYA</span>
              <div style={{ flex: 1, height: "1px", backgroundColor: "var(--border-default)" }} />
            </div>

            <button
              type="button"
              onClick={handleMetaMask}
              style={{
                padding: "10px",
                backgroundColor: "var(--bg-subtle)",
                color: "var(--text-main)",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px"
              }}
            >
              🦊 Web3 Cüzdan ile Doğrula (MetaMask)
            </button>

            <button
              type="button"
              onClick={() => { quickDemoLogin(); if (onComplete) onComplete(); }}
              style={{
                padding: "9px",
                backgroundColor: "transparent",
                color: "#60a5fa",
                border: "1px dashed var(--border-accent)",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              ⚡ Hızlı Egemen Kimlik ile Devam Et
            </button>
          </form>
        )}

        {/* 2. REGISTER MODE */}
        {mode === "register" && !newIdentity && (
          <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "4px" }}>
                Ad Soyad
              </label>
              <input
                type="text"
                value={regName}
                onChange={(e) => setRegName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "13px"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "4px" }}>
                Ulusal Kimlik No / eIDAS Ref
              </label>
              <input
                type="text"
                value={regNationalId}
                onChange={(e) => setRegNationalId(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "13px"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "4px" }}>
                E-Posta Adresi
              </label>
              <input
                type="email"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "13px"
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "4px" }}>
                Kurum / Çatı Çerçeve
              </label>
              <input
                type="text"
                value={regOrganization}
                onChange={(e) => setRegOrganization(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "13px"
                }}
              />
            </div>

            <button
              type="submit"
              style={{
                marginTop: "10px",
                padding: "10px",
                backgroundColor: "var(--color-primary)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              🔐 Kriptografik Kimlik & Anahtar Çifti Üret
            </button>
          </form>
        )}

        {/* 2B. NEW IDENTITY CREATED */}
        {mode === "register" && newIdentity && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{
              padding: "12px",
              borderRadius: "8px",
              backgroundColor: "rgba(22, 163, 74, 0.12)",
              border: "1px solid rgba(22, 163, 74, 0.3)",
              color: "#4ade80",
              fontSize: "13px",
              fontWeight: "600"
            }}>
              ✓ Egemen Kimliğiniz Başarıyla Oluşturuldu
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "4px" }}>
                W3C DID Kimliği
              </label>
              <div style={{
                padding: "8px",
                backgroundColor: "var(--bg-input)",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
                fontFamily: "var(--font-mono)",
                fontSize: "11px",
                color: "#60a5fa",
                wordBreak: "break-all"
              }}>
                {newIdentity.did}
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: "600", color: "#f59e0b", marginBottom: "4px" }}>
                ⚠️ 12 Kelimelik Kurtarma Tohum İfadesi (Bunu Güvenli Bir Yere Kaydedin)
              </label>
              <div style={{
                padding: "12px",
                backgroundColor: "rgba(245, 158, 11, 0.08)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                borderRadius: "6px",
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
                padding: "8px",
                backgroundColor: "var(--bg-subtle)",
                color: "var(--text-main)",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
                fontSize: "12px",
                cursor: "pointer"
              }}
            >
              {copied ? "✓ Kopyalandı!" : "📋 Tohum İfadesini Kopyala"}
            </button>

            <button
              type="button"
              onClick={() => { if (onComplete) onComplete(); }}
              style={{
                padding: "10px",
                backgroundColor: "var(--color-primary)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Cüzdanıma Devam Et
            </button>
          </div>
        )}

        {/* 3. SEED LOGIN */}
        {mode === "seed" && (
          <form onSubmit={handleSeedLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                12 veya 24 Kelimelik Kurtarma İfadesi
              </label>
              <textarea
                value={seedPhraseInput}
                onChange={(e) => setSeedPhraseInput(e.target.value)}
                placeholder="apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard..."
                rows={4}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "12px",
                  fontFamily: "var(--font-mono)",
                  lineHeight: "1.5",
                  resize: "vertical"
                }}
              />
            </div>

            <button
              type="submit"
              style={{
                padding: "10px",
                backgroundColor: "var(--color-primary)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Kimliği Kurtar ve Giriş Yap
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
