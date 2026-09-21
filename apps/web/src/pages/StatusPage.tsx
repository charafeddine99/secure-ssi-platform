import { useState } from "react";
import { Navbar } from "../components/layout/Navbar";
import { Sidebar, NavSection } from "../components/layout/Sidebar";

export function StatusPage() {
  const [activeSection, setActiveSection] = useState<NavSection>("dashboard");
  const [isWalletConnected, setIsWalletConnected] = useState<boolean>(true);
  const [walletAddress, setWalletAddress] = useState<string>("0x71C2a8F8bC1623b3781290aE201b22308947bE09");
  const [userDid, setUserDid] = useState<string>("did:key:z6MkuBesnaStudentKey2026SUBUEVM");

  const handleToggleWallet = () => {
    setIsWalletConnected(!isWalletConnected);
  };

  return (
    <div className="app-shell">
      {/* 1. ÜST BAR (NAVBAR) */}
      <Navbar
        isWalletConnected={isWalletConnected}
        onToggleWallet={handleToggleWallet}
        walletAddress={walletAddress}
        userDid={userDid}
      />

      <div className="app-body">
        {/* 2. SOL GEZİNME MENÜSÜ (SIDEBAR) */}
        <Sidebar
          activeSection={activeSection}
          onSelectSection={(section) => setActiveSection(section)}
        />

        {/* 3. ANA ÇALIŞMA ALANI */}
        <main className="app-content">
          {activeSection === "dashboard" && (
            <section>
              <div className="page-header">
                <h1>Platform Genel Bakış & Sistem Durumu</h1>
                <p>
                  Sakarya Uygulamalı Bilimler Üniversitesi - SSI, Yapay Zekâ, Blockchain ve Acil Kurtarma Altyapısı
                </p>
              </div>

              {/* KPI KARTLARI */}
              <div className="grid-4" style={{ marginBottom: "24px" }}>
                <div className="web3-card" style={{ padding: "18px" }}>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: "6px" }}>Aktif DID / Cüzdan</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: "bold", color: "var(--accent-cyan)" }}>1,248</div>
                  <div style={{ fontSize: "0.75rem", color: "#34d399", marginTop: "4px" }}>↑ %12 bu hafta</div>
                </div>

                <div className="web3-card" style={{ padding: "18px" }}>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: "6px" }}>Düzenlenen VC (Diplomalar)</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#818cf8" }}>3,892</div>
                  <div style={{ fontSize: "0.75rem", color: "#34d399", marginTop: "4px" }}>W3C VC 2.0</div>
                </div>

                <div className="web3-card" style={{ padding: "18px" }}>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: "6px" }}>AI Doğruluk Oranı</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#34d399" }}>%94.3</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>XGBoost + Autoencoder</div>
                </div>

                <div className="web3-card" style={{ padding: "18px" }}>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: "6px" }}>Kurtarma Quorumu</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: "bold", color: "var(--accent-yellow)" }}>3 / 5</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>Shamir Secret Sharing</div>
                </div>
              </div>

              {/* 4 ANA KATMAN ÇALIŞMA DURUMU */}
              <div className="web3-card">
                <div className="card-title-group">
                  <h2>4 Katmanlı Mimari Servis Canlılık Durumu</h2>
                  <p>Arka plandaki mikroservislerin ve akıllı sözleşmelerin durumu:</p>
                </div>

                <div className="grid-2">
                  <div style={{ padding: "16px", background: "#081120", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <strong>1. SSI & Kimlik Yönetimi</strong>
                      <span className="badge-green">ÇALIŞIYOR (Port 8001)</span>
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
                      W3C VC 2.0, DID resolution, 131.072 bitlik Status List ve MongoDB entegrasyonu aktif.
                    </p>
                  </div>

                  <div style={{ padding: "16px", background: "#081120", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <strong>2. AI Fraud Detection Motoru</strong>
                      <span className="badge-green">ÇALIŞIYOR (Port 8002)</span>
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
                      XGBoost + Autoencoder ile gerçek zamanlı davranış analizi, anomali tespiti ve otomatik karantina.
                    </p>
                  </div>

                  <div style={{ padding: "16px", background: "#081120", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <strong>3. Ethereum Hardhat Sözleşmeleri</strong>
                      <span className="badge-green">DAĞITILDI (#1337)</span>
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
                      DIDRegistry, RevocationRegistry, EmergencyRecovery (EIP-4337) ve AuditLogger EVM üzerinde hazır.
                    </p>
                  </div>

                  <div style={{ padding: "16px", background: "#081120", borderRadius: "12px", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <strong>4. Acil Durum Sosyal Kurtarma</strong>
                      <span className="badge-green">ÇALIŞIYOR (Port 8003)</span>
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
                      3/5 Guardian onayı, Shamir Secret Sharing, Time-lock süresi ve otomatik anahtar rotasyonu devrede.
                    </p>
                  </div>
                </div>
              </div>
            </section>
          )}

          {activeSection === "wallet" && (
            <section>
              <div className="page-header">
                <h1>Kimlik Cüzdanım (Holder Wallet)</h1>
                <p>Sahip olduğunuz W3C Verifiable Credentials (VC) ve DID belgelerini yönetin.</p>
              </div>
              <div className="web3-card">
                <div className="card-title-group">
                  <h2>Bu modül ADIM 2'de canlı W3C kartları, QR kod ve DID üretici ile detaylandırılacaktır.</h2>
                </div>
              </div>
            </section>
          )}

          {activeSection === "issuer" && (
            <section>
              <div className="page-header">
                <h1>Belge Düzenleyici (Issuer Portal)</h1>
                <p>SUBÜ adına öğrenci ve mezunlara dijital diploma (VC) üretin ve imzalayın.</p>
              </div>
              <div className="web3-card">
                <div className="card-title-group">
                  <h2>Bu modül ADIM 3'te dinamik diploma düzenleyici ve imzalama motoru ile detaylandırılacaktır.</h2>
                </div>
              </div>
            </section>
          )}

          {activeSection === "verifier" && (
            <section>
              <div className="page-header">
                <h1>Doğrulayıcı Portal (Verifier)</h1>
                <p>Sunulan diplomaları ve ZKP kanıtlarını (GPA &gt;= 3.0) anında doğrulayın.</p>
              </div>
              <div className="web3-card">
                <div className="card-title-group">
                  <h2>Bu modül ADIM 4'te canlı ZKP seçici açıklama doğrulayıcısı ile detaylandırılacaktır.</h2>
                </div>
              </div>
            </section>
          )}

          {activeSection === "ai" && (
            <section>
              <div className="page-header">
                <h1>Yapay Zekâ Güvenlik Merkezi (AI Fraud Monitor)</h1>
                <p>XGBoost + Autoencoder modeliyle işlem risklerini ve anomali uyarılarını izleyin.</p>
              </div>
              <div className="web3-card">
                <div className="card-title-group">
                  <h2>Bu modül ADIM 5'te canlı backend API'sine bağlı siber savunma paneli olarak detaylandırılacaktır.</h2>
                </div>
              </div>
            </section>
          )}

          {activeSection === "recovery" && (
            <section>
              <div className="page-header">
                <h1>3/5 Guardian Acil Durum Kurtarma</h1>
                <p>Cihaz veya özel anahtar kaybında kimliğinizi 3/5 Guardian onayı ile geri kazanın.</p>
              </div>
              <div className="web3-card">
                <div className="card-title-group">
                  <h2>Bu modül ADIM 6'da interaktif Guardian onay paneli ve Time-lock sayacı ile detaylandırılacaktır.</h2>
                </div>
              </div>
            </section>
          )}

          {activeSection === "blockchain" && (
            <section>
              <div className="page-header">
                <h1>Blockchain Denetim Defteri (Ledger Explorer)</h1>
                <p>Hardhat Ethereum ağındaki 4 akıllı sözleşmenin işlemlerini ve gas harcamalarını inceleyin.</p>
              </div>
              <div className="web3-card">
                <div className="card-title-group">
                  <h2>Bu modül ADIM 7'de zincir işlem günlüğü tablosu ile detaylandırılacaktır.</h2>
                </div>
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
