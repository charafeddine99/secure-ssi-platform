import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";

interface AuthModalProps {
  isOpen: boolean;
  onClose?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login, register, loginWithMetaMask, loginWithSeedPhrase, quickDemoLogin } = useAuth();
  const [activeTab, setActiveTab] = useState<"login" | "register" | "seed">("login");

  // Login form state
  const [loginEmail, setLoginEmail] = useState("b210109591@subu.edu.tr");
  const [loginPassword, setLoginPassword] = useState("123456");

  // Register form state
  const [regName, setRegName] = useState("Charaf Eddine Bessanane");
  const [regStudentId, setRegStudentId] = useState("B210109591");
  const [regEmail, setRegEmail] = useState("b210109591@subu.edu.tr");
  const [regDepartment, setRegDepartment] = useState("Bilgisayar Mühendisliği");
  const [regPassword, setRegPassword] = useState("123456");

  // Seed login state
  const [seedInput, setSeedInput] = useState("");

  // Newly registered seed reveal state
  const [createdCredentials, setCreatedCredentials] = useState<{
    did: string;
    seedPhrase: string;
    walletAddress: string;
  } | null>(null);

  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  if (!isOpen) return null;

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFeedbackError(null);
    if (!loginEmail) {
      setFeedbackError("Lütfen e-posta veya DID adresinizi girin.");
      return;
    }
    login(loginEmail, loginPassword);
    if (onClose) onClose();
  };

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFeedbackError(null);
    if (!regName || !regEmail) {
      setFeedbackError("Lütfen adınızı ve e-posta adresinizi doldurun.");
      return;
    }
    const result = register(regName, regStudentId, regEmail, regDepartment, regPassword);
    setCreatedCredentials({
      did: result.user.did,
      seedPhrase: result.seedPhrase,
      walletAddress: result.user.walletAddress
    });
  };

  const handleSeedSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFeedbackError(null);
    if (!seedInput.trim()) {
      setFeedbackError("Lütfen 12 kelimelik güvenlik ifadenizi girin.");
      return;
    }
    const success = loginWithSeedPhrase(seedInput);
    if (success) {
      if (onClose) onClose();
    } else {
      setFeedbackError("Geçersiz güvenlik ifadesi. En az 12 kelime giriniz.");
    }
  };

  const handleMetaMaskLogin = async () => {
    setFeedbackError(null);
    const success = await loginWithMetaMask();
    if (success) {
      if (onClose) onClose();
    } else {
      setFeedbackError("MetaMask bağlantısı başarısız oldu. Lütfen eklentinizi açın veya demo modunu kullanın.");
    }
  };

  const handleQuickDemo = () => {
    quickDemoLogin();
    if (onClose) onClose();
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
                <span>✓</span> Kimliğiniz ve Kriptografik Anahtar Çiftiniz Başarıyla Üretildi!
              </span>
              <p className="text-[11px] text-slate-300">
                Aşağıdaki 12 kelimelik güvenlik ifadesi cüzdanınızın kurtarma anahtarıdır. Lütfen bu kelimeleri güvenli bir yere kaydediniz.
              </p>
            </div>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-slate-400 block mb-1 text-[11px]">Üretilen W3C DID:</span>
                <p className="font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-indigo-400 text-[11px] break-all">
                  {createdCredentials.did}
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
                  <span className="text-slate-400 text-[11px]">12 Kelimelik Kurtarma İfadesi (Seed Phrase):</span>
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
              </div>
            </div>

            <button
              onClick={() => {
                setCreatedCredentials(null);
                if (onClose) onClose();
              }}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition"
            >
              Cüzdanıma ve Kontrol Paneline Gir →
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
              <button
                onClick={() => setActiveTab("register")}
                className={`flex-1 py-2 rounded-lg transition ${
                  activeTab === "register"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Yeni Hesap / DID Oluştur
              </button>
              <button
                onClick={() => setActiveTab("seed")}
                className={`flex-1 py-2 rounded-lg transition ${
                  activeTab === "seed"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Tohum ile Kurtar
              </button>
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
                    placeholder="b210109591@subu.edu.tr"
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
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition mt-2"
                >
                  Giriş Yap
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
                  <button
                    type="button"
                    onClick={handleMetaMaskLogin}
                    className="py-2.5 px-3 bg-slate-800 hover:bg-slate-700 border border-slate-700/60 rounded-xl text-[11px] font-medium text-slate-200 hover:text-white transition flex items-center justify-center gap-1.5"
                  >
                    <span>🦊</span>
                    <span>MetaMask Girişi</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleQuickDemo}
                    className="py-2.5 px-3 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 rounded-xl text-[11px] font-medium text-emerald-300 transition flex items-center justify-center gap-1.5"
                  >
                    <span>⚡</span>
                    <span>Hızlı Demo Girişi</span>
                  </button>
                </div>
              </form>
            )}

            {/* Tab 2: Register */}
            {activeTab === "register" && (
              <form onSubmit={handleRegisterSubmit} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 text-xs block mb-1">Ad Soyad</label>
                    <input
                      type="text"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      placeholder="Charaf Eddine Bessanane"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 text-xs block mb-1">Öğrenci No</label>
                    <input
                      type="text"
                      value={regStudentId}
                      onChange={(e) => setRegStudentId(e.target.value)}
                      placeholder="B210109591"
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
                    placeholder="b210109591@subu.edu.tr"
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
                  Kriptografik DID ve Cüzdan Üret →
                </button>
              </form>
            )}

            {/* Tab 3: Seed Recovery Login */}
            {activeTab === "seed" && (
              <form onSubmit={handleSeedSubmit} className="space-y-3.5">
                <div>
                  <label className="text-slate-400 text-xs block mb-1">12 Kelimelik Kurtarma İfadeniz</label>
                  <textarea
                    rows={3}
                    value={seedInput}
                    onChange={(e) => setSeedInput(e.target.value)}
                    placeholder="kelime1 kelime2 kelime3 kelime4 ... kelime12"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl p-3 text-xs text-white font-mono outline-none"
                  />
                </div>

                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-slate-400 space-y-1">
                  <p>• Cihazınızı değiştirdiğinizde veya kaybettiğinizde anahtarlarınızı kurtarır.</p>
                  <p>• Şifreli tohum üzerinden yeni oturum anahtarları üretilir.</p>
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition"
                >
                  Kimliği Kurtar ve Giriş Yap
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
};
