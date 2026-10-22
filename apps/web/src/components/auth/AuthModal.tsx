import React, { useState } from "react";
import { DEMO_AUTH_ENABLED, useAuth } from "../../context/AuthContext";

interface AuthModalProps {
  isOpen: boolean;
  onClose?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login, register, quickDemoLogin, isAuthLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<"login" | "register">("login");

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Register form state
  const [regName, setRegName] = useState("");
  const [regStudentId, setRegStudentId] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regDepartment, setRegDepartment] = useState("");
  const [regPassword, setRegPassword] = useState("");

  // Newly registered seed reveal state
  const [createdCredentials, setCreatedCredentials] = useState<{
    did: string;
    seedPhrase: string;
    walletAddress: string;
  } | null>(null);

  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  if (!isOpen) return null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedbackError(null);
    if (!loginEmail) {
      setFeedbackError("Lütfen e-posta veya DID adresinizi girin.");
      return;
    }
    try {
      if (await login(loginEmail, loginPassword)) {
        if (onClose) onClose();
      } else {
        setFeedbackError("Authentication failed. Please verify your credentials.");
      }
    } catch {
      setFeedbackError("Identity Service could not complete sign-in. Check the service and try again.");
    }
  };

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFeedbackError(null);
    if (!regName || !regEmail) {
      setFeedbackError("Lütfen adınızı ve e-posta adresinizi doldurun.");
      return;
    }
    try {
      const result = register(regName, regStudentId, regEmail, regDepartment, regPassword);
      setCreatedCredentials({
        did: result.user.did,
        seedPhrase: result.seedPhrase,
        walletAddress: result.user.walletAddress
      });
    } catch {
      setFeedbackError("Local demo wallet creation is not enabled in this build.");
    }
  };

  const handleQuickDemo = async () => {
    try {
      if (await quickDemoLogin() && onClose) onClose();
      else setFeedbackError("Demo sign-in is unavailable. Check the development demo-auth setting and Identity Service.");
    } catch {
      setFeedbackError("Identity Service could not complete sign-in. Check the service and try again.");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute -top-20 -left-20 w-48 h-48 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none"></div>

        {/* Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 mx-auto flex items-center justify-center text-xl shadow-lg shadow-indigo-500/30 mb-3">
            🛡️
          </div>
          <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight">
            Secure SSI Platform
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Sakarya Uygulamalı Bilimler Üniversitesi • Bilgisayar Mühendisliği Tasarımı
          </p>
        </div>

        {/* If newly created credentials are being displayed */}
        {createdCredentials ? (
          <div className="space-y-4 animate-fade-in">
            <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl">
              <span className="text-emerald-400 font-bold text-xs flex items-center gap-1.5 mb-1">
                <span>✓</span> Yerel demo cüzdanı oluşturuldu; backend hesabı veya DID oluşturulmadı.
              </span>
              <p className="text-[11px] text-slate-300">
                Aşağıdaki 12 kelimelik güvenlik ifadesi cüzdanınızın kurtarma anahtarıdır. Lütfen bu kelimeleri güvenli bir yere kaydediniz.
              </p>
            </div>

            <div className="space-y-2 text-xs">
              <div>
              <span className="text-slate-400 block mb-1 text-[11px]">Sentetik DID örneği (kayıtlı değil):</span>
                <p className="font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-indigo-400 text-[11px] break-all">
                  {createdCredentials.did || "Identity Service tarafından atanmadı."}
                </p>
              </div>

              <div>
                <span className="text-slate-400 block mb-1 text-[11px]">Cüzdan Adresi:</span>
                <p className="font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-slate-300 text-[11px] break-all">
                  {createdCredentials.walletAddress}
                </p>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-slate-400 text-[11px]">Tek seferlik demo cüzdan ifadesi (uygulama içi geri yükleme yok):</span>
                  <button
                    onClick={() => copyToClipboard(createdCredentials.seedPhrase)}
                    className="text-indigo-400 hover:text-indigo-300 text-[11px] font-medium"
                  >
                    {isCopied ? "Kopyalandı ✓" : "Kopyala"}
                  </button>
                </div>
                <p className="font-mono bg-amber-500/10 p-3 rounded-xl border border-amber-500/20 text-amber-200 text-xs font-semibold leading-relaxed break-words">
                  {createdCredentials.seedPhrase}
                </p>
                <p className="text-amber-300 text-[11px] mt-2">Bu ifade uygulama tarafından saklanmaz. Uygulama içinden cüzdanı geri yükleme ve backend hesabı oluşturma desteklenmiyor.</p>
              </div>
            </div>

            <button
              onClick={() => {
                setCreatedCredentials(null);
                setActiveTab("login");
              }}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition"
            >
              Giriş ekranına dön
            </button>
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div className="flex rounded-xl bg-slate-950 p-1 border border-slate-800 mb-5 text-xs font-medium">
              <button
                onClick={() => setActiveTab("login")}
                className={`flex-1 py-2 rounded-lg transition ${
                  activeTab === "login"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Giriş Yap
              </button>
              {DEMO_AUTH_ENABLED && <button
                onClick={() => setActiveTab("register")}
                className={`flex-1 py-2 rounded-lg transition ${
                  activeTab === "register"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Yerel demo profili oluştur
              </button>}
            </div>

            {/* Error banner */}
            {feedbackError && (
              <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex justify-between items-center">
                <span>{feedbackError}</span>
                <button onClick={() => setFeedbackError(null)} className="font-bold ml-2">✕</button>
              </div>
            )}

            {/* Tab 1: Login */}
            {activeTab === "login" && (
              <form onSubmit={handleLoginSubmit} className="space-y-3.5">
                <div>
                  <label className="text-slate-400 text-xs block mb-1">E-posta veya DID</label>
                  <input
                    type="text"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="name@example.test"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white outline-none transition"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs block mb-1">Şifre / PIN</label>
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white outline-none transition"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isAuthLoading}
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition mt-2"
                >
                  {isAuthLoading ? "Giriş yapılıyor…" : "Giriş Yap"}
                </button>

                <div className="relative my-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-800"></div>
                  </div>
                  <div className="relative flex justify-center text-[10px] uppercase">
                    <span className="bg-slate-900 px-2 text-slate-500">veya</span>
                  </div>
                </div>

                {/* Alternative Quick Logins */}
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" disabled className="py-2.5 px-3 bg-slate-800 border border-slate-700/60 rounded-xl text-[11px] font-medium text-slate-400 cursor-not-allowed">
                    🦊 Cüzdanla giriş desteklenmiyor (imzalı nonce doğrulaması yok)
                  </button>

                  {DEMO_AUTH_ENABLED && <button
                    type="button"
                    onClick={handleQuickDemo}
                    className="py-2.5 px-3 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 rounded-xl text-[11px] font-medium text-emerald-300 transition flex items-center justify-center gap-1.5"
                  >
                    <span>⚡</span>
                    <span>Hızlı Demo Girişi</span>
                  </button>}
                </div>
              </form>
            )}

            {/* Tab 2: Register */}
            {activeTab === "register" && DEMO_AUTH_ENABLED && (
              <form onSubmit={handleRegisterSubmit} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 text-xs block mb-1">Ad Soyad</label>
                    <input
                      type="text"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      placeholder="Synthetic demo name"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 text-xs block mb-1">Öğrenci No</label>
                    <input
                      type="text"
                      value={regStudentId}
                      onChange={(e) => setRegStudentId(e.target.value)}
                    placeholder="DEMO-0001"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-slate-400 text-xs block mb-1">Kurumsal E-posta</label>
                  <input
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="name@example.test"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs block mb-1">Bölüm</label>
                  <input
                    type="text"
                    value={regDepartment}
                    onChange={(e) => setRegDepartment(e.target.value)}
                    placeholder="Bilgisayar Mühendisliği"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs block mb-1">Şifre / PIN</label>
                  <input
                    type="password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition mt-2"
                >
                  Yerel demo cüzdan profili oluştur →
                </button>
              </form>
            )}

          </>
        )}
      </div>
    </div>
  );
};
