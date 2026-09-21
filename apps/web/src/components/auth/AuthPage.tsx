import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";

export const AuthPage: React.FC<{ onComplete?: () => void }> = ({ onComplete }) => {
  const { login, register, loginWithMetaMask, loginWithSeedPhrase, quickDemoLogin } = useAuth();
  const [mode, setMode] = useState<"login" | "register" | "seed">("login");

  // Login form
  const [loginEmail, setLoginEmail] = useState("b210109591@subu.edu.tr");
  const [loginPassword, setLoginPassword] = useState("123456");

  // Register form
  const [regName, setRegName] = useState("Charaf Eddine Bessanane");
  const [regStudentId, setRegStudentId] = useState("B210109591");
  const [regEmail, setRegEmail] = useState("b210109591@subu.edu.tr");
  const [regDepartment, setRegDepartment] = useState("Bilgisayar Mühendisliği");
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
    const res = register(regName, regStudentId, regEmail, regDepartment, regPassword);
    setNewIdentity({
      did: res.user.did,
      seedPhrase: res.seedPhrase,
      walletAddress: res.user.walletAddress
    });
  };

  const handleSeedLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    const success = loginWithSeedPhrase(seedPhraseInput);
    if (success) {
      if (onComplete) onComplete();
    } else {
      setErrorMsg("Geçersiz güvenlik ifadesi. En az 12 kelimelik tohum giriniz.");
    }
  };

  const handleMetaMask = async () => {
    setErrorMsg(null);
    const success = await loginWithMetaMask();
    if (success) {
      if (onComplete) onComplete();
    } else {
      setErrorMsg("MetaMask cüzdanına bağlanılamadı. Lütfen eklentinizi açın veya demo girişini kullanın.");
    }
  };

  const handleQuickDemo = () => {
    quickDemoLogin();
    if (onComplete) onComplete();
  };

  const copyText = (val: string) => {
    navigator.clipboard.writeText(val);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center items-center p-4 relative overflow-hidden selection:bg-indigo-500 selection:text-white">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-10 right-10 w-96 h-96 bg-cyan-600/10 rounded-full blur-[100px] pointer-events-none"></div>

      {/* Main card */}
      <div className="relative z-10 w-full max-w-lg bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
        {/* University & Title Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-cyan-500 shadow-xl shadow-indigo-500/25 mb-3 text-2xl">
            🎓
          </div>
          <span className="text-[11px] font-bold uppercase tracking-widest text-indigo-400 block mb-1">
            T.C. Sakarya Uygulamalı Bilimler Üniversitesi
          </span>
          <h1 className="text-2xl font-black text-white tracking-tight">
            Secure Self-Sovereign Identity
          </h1>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed max-w-sm mx-auto">
            Yapay Zekâ Tabanlı Dolandırıcılık Tespiti ve Blokzincir Acil Kurtarma Portalı
          </p>
        </div>

        {/* If new identity created, show cryptographic seed credentials */}
        {newIdentity ? (
          <div className="space-y-4 animate-fade-in">
            <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs mb-1">
                <span>✓</span>
                <span>W3C DID ve Kriptografik Cüzdanınız Üretildi!</span>
              </div>
              <p className="text-[11px] text-slate-300">
                Aşağıdaki 12 kelimelik güvenlik tohumu cüzdanınızın kurtarma anahtarıdır. Cihazınızı kaybetseniz bile kimliğinizi bununla kurtarabilirsiniz.
              </p>
            </div>

            <div className="space-y-2.5 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px] mb-1 font-medium">Atanan W3C Decentralized Identifier (DID):</span>
                <p className="font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-indigo-300 text-[11px] break-all select-all">
                  {newIdentity.did}
                </p>
              </div>

              <div>
                <span className="text-slate-400 block text-[11px] mb-1 font-medium">EVM Cüzdan Adresi:</span>
                <p className="font-mono bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-slate-300 text-[11px] break-all">
                  {newIdentity.walletAddress}
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-slate-400 text-[11px] font-medium">12 Kelimelik Kurtarma İfadesi (Seed Phrase):</span>
                  <button
                    onClick={() => copyText(newIdentity.seedPhrase)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                  >
                    {copied ? "Kopyalandı ✓" : "Kopyala"}
                  </button>
                </div>
                <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-200 text-xs font-mono font-medium leading-relaxed select-all">
                  {newIdentity.seedPhrase}
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                setNewIdentity(null);
                if (onComplete) onComplete();
              }}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition duration-150"
            >
              Cüzdanıma ve Sisteme Giriş Yap →
            </button>
          </div>
        ) : (
          <>
            {/* Quick 1-Click Launch Banner */}
            <div className="mb-5 p-4 bg-gradient-to-r from-indigo-950 via-slate-900 to-indigo-950 border border-indigo-500/40 rounded-2xl flex items-center justify-between gap-3 shadow-xl">
              <div>
                <span className="text-[10px] font-bold uppercase text-emerald-400 tracking-wider flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  Hızlı Başlat & Sunum Modu
                </span>
                <span className="text-xs font-bold text-white block mt-0.5">
                  Charaf Eddine Bessanane (B210109591)
                </span>
                <span className="text-[10px] text-slate-400 block">
                  SUBÜ Bilgisayar Mühendisliği Tasarımı
                </span>
              </div>
              <button
                type="button"
                onClick={handleQuickDemo}
                className="px-4 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-xs rounded-xl shadow-lg shadow-emerald-500/30 transition active:scale-95 whitespace-nowrap flex items-center gap-1.5"
              >
                <span>🚀</span>
                <span>Hemen Başlat</span>
              </button>
            </div>

            {/* Mode selection tabs */}
            <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800 mb-5 text-xs font-medium">
              <button
                onClick={() => setMode("login")}
                className={`flex-1 py-2 rounded-lg transition ${
                  mode === "login"
                    ? "bg-indigo-600 text-white shadow-md"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Giriş Yap
              </button>
              <button
                onClick={() => setMode("register")}
                className={`flex-1 py-2 rounded-lg transition ${
                  mode === "register"
                    ? "bg-indigo-600 text-white shadow-md"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Yeni Hesap / DID Oluştur
              </button>
              <button
                onClick={() => setMode("seed")}
                className={`flex-1 py-2 rounded-lg transition ${
                  mode === "seed"
                    ? "bg-indigo-600 text-white shadow-md"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Kurtarma İfadesi
              </button>
            </div>

            {/* Error banner */}
            {errorMsg && (
              <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex items-center justify-between">
                <span>{errorMsg}</span>
                <button onClick={() => setErrorMsg(null)} className="font-bold ml-2">✕</button>
              </div>
            )}

            {/* Form 1: Login */}
            {mode === "login" && (
              <form onSubmit={handleLogin} className="space-y-3.5">
                <div>
                  <label className="text-slate-400 text-xs block mb-1 font-medium">Kurumsal E-posta veya DID</label>
                  <input
                    type="text"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="b210109591@subu.edu.tr"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white outline-none transition"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs block mb-1 font-medium">Şifre / PIN</label>
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
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition duration-150 mt-1"
                >
                  Giriş Yap
                </button>

                <div className="relative my-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-800"></div>
                  </div>
                  <div className="relative flex justify-center text-[10px] uppercase">
                    <span className="bg-slate-900 px-2 text-slate-500 font-medium">veya tek tıkla bağlan</span>
                  </div>
                </div>

                {/* Quick login options */}
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={handleMetaMask}
                    className="py-2.5 px-3 bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 rounded-xl text-[11px] font-medium text-slate-200 hover:text-white transition flex items-center justify-center gap-1.5 shadow-sm"
                  >
                    <span>🦊</span>
                    <span>MetaMask Girişi</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleQuickDemo}
                    className="py-2.5 px-3 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 rounded-xl text-[11px] font-semibold text-emerald-300 transition flex items-center justify-center gap-1.5 shadow-sm"
                  >
                    <span>⚡</span>
                    <span>Hızlı Demo Girişi</span>
                  </button>
                </div>
              </form>
            )}

            {/* Form 2: Register */}
            {mode === "register" && (
              <form onSubmit={handleRegister} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 text-xs block mb-1 font-medium">Ad Soyad</label>
                    <input
                      type="text"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      placeholder="Charaf Eddine Bessanane"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 text-xs block mb-1 font-medium">Öğrenci Numarası</label>
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
                  <label className="text-slate-400 text-xs block mb-1 font-medium">SUBÜ Kurumsal E-posta</label>
                  <input
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="b210109591@subu.edu.tr"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs block mb-1 font-medium">Fakülte / Bölüm</label>
                  <input
                    type="text"
                    value={regDepartment}
                    onChange={(e) => setRegDepartment(e.target.value)}
                    placeholder="Bilgisayar Mühendisliği"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 text-xs block mb-1 font-medium">Cüzdan Şifresi (Yerel Koruma)</label>
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
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition duration-150 mt-2"
                >
                  Kriptografik DID ve Cüzdan Üret →
                </button>
              </form>
            )}

            {/* Form 3: Seed phrase login */}
            {mode === "seed" && (
              <form onSubmit={handleSeedLogin} className="space-y-3.5">
                <div>
                  <label className="text-slate-400 text-xs block mb-1 font-medium">12 Kelimelik Kurtarma İfadeniz</label>
                  <textarea
                    rows={3}
                    value={seedPhraseInput}
                    onChange={(e) => setSeedPhraseInput(e.target.value)}
                    placeholder="apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard"
                    className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl p-3 text-xs text-white font-mono outline-none"
                  />
                </div>

                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-slate-400 space-y-1">
                  <p>• Cihazınızı kaybettiğinizde veya yeni bir cihaza geçtiğinizde kimliğinizi yükler.</p>
                  <p>• Deterministik anahtar türetimi ile W3C kimlik kaydınız yeniden açılır.</p>
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition duration-150"
                >
                  Kimliği Kurtar ve Giriş Yap
                </button>
              </form>
            )}
          </>
        )}

        {/* Footer credits */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 text-center text-[10px] text-slate-500">
          Charaf Eddine Bessanane • Danışman: Dr. Öğr. Üyesi A. F. M. Suaib Akhter
        </div>
      </div>
    </div>
  );
};
