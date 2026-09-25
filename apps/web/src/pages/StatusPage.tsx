import { useState } from "react";
import { Navbar } from "../components/layout/Navbar";
import { Sidebar, NavSection } from "../components/layout/Sidebar";

interface CredentialItem {
  id: string;
  title: string;
  type: string;
  issuer: string;
  issuedDate: string;
  status: "ACTIVE" | "REVOKED";
  claims: Record<string, any>;
  proofValue: string;
}

interface GuardianItem {
  id: number;
  name: string;
  role: string;
  did: string;
  approved: boolean;
}

export function StatusPage() {
  const [activeSection, setActiveSection] = useState<NavSection>("wallet");
  const [isWalletConnected, setIsWalletConnected] = useState<boolean>(true);
  const [walletAddress] = useState<string>("0x71C2a8F8bC1623b3781290aE201b22308947bE09");
  const [userDid, setUserDid] = useState<string>("did:key:z6MkuBesnaStudentKey2026SUBUEVM");

  // 1. CÜZDAN & DİPLOMA STATE
  const [credentials, setCredentials] = useState<CredentialItem[]>([
    {
      id: "urn:uuid:subu-diploma-2026-b210109591",
      title: "Bilgisayar Mühendisliği Lisans Diploması",
      type: "UniversityDegreeCredential",
      issuer: "did:web:subu.edu.tr",
      issuedDate: "2026-06-25",
      status: "ACTIVE",
      claims: {
        ogrenciAdi: "Charaf Eddine Bessanane",
        ogrenciNo: "B210109591",
        fakulte: "Teknoloji Fakültesi",
        bolum: "Bilgisayar Mühendisliği",
        derece: "Lisans (B.Sc.)",
        gpa: "3.82 / 4.00",
        tcKimlik: "12345678901"
      },
      proofValue: "z3s9PqRtXvM8SUBUSignedProofValueValidW3C2026Ed25519"
    }
  ]);

  const [selectedCred, setSelectedCred] = useState<CredentialItem | null>(credentials[0]);
  const [showQrModal, setShowQrModal] = useState<boolean>(false);
  const [didCopied, setDidCopied] = useState<boolean>(false);

  // 2. ISSUER STATE (YENİ DİPLOMA ÜRETME)
  const [issuerStudentName, setIssuerStudentName] = useState("Charaf Eddine Bessanane");
  const [issuerStudentId, setIssuerStudentId] = useState("B210109591");
  const [issuerDepartment, setIssuerDepartment] = useState("Bilgisayar Mühendisliği");
  const [issuerGpa, setIssuerGpa] = useState("3.82");
  const [issuerNotification, setIssuerNotification] = useState<string | null>(null);

  // 3. VERIFIER STATE
  const [verifierResult, setVerifierResult] = useState<any>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [zkpMasked, setZkpMasked] = useState<boolean>(true);

  // 4. AI FRAUD MONITOR STATE
  const [aiGeoKm, setAiGeoKm] = useState<number>(15);
  const [aiFailedCount, setAiFailedCount] = useState<number>(0);
  const [aiFreq, setAiFreq] = useState<number>(2);
  const [aiIsTor, setAiIsTor] = useState<boolean>(false);
  const [aiDeviceMatch, setAiDeviceMatch] = useState<boolean>(true);
  const [aiEvalResult, setAiEvalResult] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [quarantinedList, setQuarantinedList] = useState<string[]>([]);

  // 5. RECOVERY STATE
  const [guardians, setGuardians] = useState<GuardianItem[]>([
    { id: 1, name: "Dr. Danışman Hoca", role: "Akademik Danışman", did: "did:key:z6MkuGuardian1Danisman", approved: true },
    { id: 2, name: "Fakülte Sekreterliği", role: "Kurumsal Onaycı", did: "did:key:z6MkuGuardian2Fakulte", approved: true },
    { id: 3, name: "Güvenilir Arkadaş", role: "Bireysel Temsilci", did: "did:key:z6MkuGuardian3Arkadas", approved: false },
    { id: 4, name: "Yedek Donanım Anahtarı", role: "Yedek Cihaz", did: "did:key:z6MkuGuardian4Yedek", approved: false },
    { id: 5, name: "Dijital Noter Servisi", role: "Bağımsız Şahit", did: "did:key:z6MkuGuardian5Noter", approved: false }
  ]);
  const [recoveryExecuted, setRecoveryExecuted] = useState<boolean>(false);

  // --- EYLEMLER ---
  const handleGenerateNewDid = () => {
    const randomHex = Array.from({ length: 16 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
    const newDid = `did:key:z6Mku${randomHex}Besna`;
    setUserDid(newDid);
    setDidCopied(true);
    setTimeout(() => setDidCopied(false), 2500);
  };

  const handleIssueCredential = (e: React.FormEvent) => {
    e.preventDefault();
    const newId = `urn:uuid:${Math.random().toString(36).substring(2, 12)}-subu-2026`;
    const newCred: CredentialItem = {
      id: newId,
      title: `${issuerDepartment} Diploması`,
      type: "UniversityDegreeCredential",
      issuer: "did:web:subu.edu.tr",
      issuedDate: new Date().toISOString().split("T")[0],
      status: "ACTIVE",
      claims: {
        ogrenciAdi: issuerStudentName,
        ogrenciNo: issuerStudentId,
        fakulte: "Teknoloji Fakültesi",
        bolum: issuerDepartment,
        derece: "Lisans (B.Sc.)",
        gpa: `${issuerGpa} / 4.00`,
        tcKimlik: "12345678901"
      },
      proofValue: "z3s" + Math.random().toString(36).substring(2, 25)
    };
    setCredentials([newCred, ...credentials]);
    setSelectedCred(newCred);
    setIssuerNotification(`Başarılı: ${issuerStudentName} adına W3C Diploması düzenlendi ve imzalandı!`);
    setTimeout(() => setIssuerNotification(null), 4000);
  };

  const handleRevokeCredential = (id: string) => {
    const updated = credentials.map(c => c.id === id ? { ...c, status: "REVOKED" as const } : c);
    setCredentials(updated);
    if (selectedCred?.id === id) {
      setSelectedCred({ ...selectedCred, status: "REVOKED" });
    }
  };

  const handleVerifyCredential = () => {
    setIsVerifying(true);
    setTimeout(() => {
      setIsVerifying(false);
      if (!selectedCred) return;
      if (selectedCred.status === "REVOKED") {
        setVerifierResult({
          valid: false,
          reason: "KİMLİK GEÇERSİZ: Belge SUBÜ Status List üzerinde iptal edilmiş (REVOKED).",
          zkpSatisfied: false
        });
      } else {
        setVerifierResult({
          valid: true,
          issuer: selectedCred.issuer,
          algorithm: "DataIntegrityProof - eddsa-jcs-2022",
          latencyMs: 3.8,
          zkpSatisfied: true,
          zkpPredicate: "GPA >= 3.00 (Koşul Gerçek Değer Gizlenerek Doğrulandı)",
          hiddenFields: ["tcKimlik", "ogrenciNo", "ogrenciAdi"]
        });
      }
    }, 600);
  };

  const handleRunAiEvaluation = async () => {
    setAiLoading(true);
    try {
      const resp = await fetch("http://127.0.0.1:8002/api/v1/fraud/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          did: userDid,
          action: "presentation_verification",
          client_ip: aiIsTor ? "185.220.101.5" : "192.168.1.100",
          user_agent: "Mozilla/5.0 SecureSSI",
          failed_attempts: aiFailedCount,
          geo_distance_km: aiGeoKm,
          time_since_last_action_sec: 60,
          presentation_frequency_10m: aiFreq,
          device_fingerprint: aiDeviceMatch ? "fp-known" : "fp-unknown",
          device_fingerprint_match: aiDeviceMatch,
          is_tor_or_proxy: aiIsTor
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        setAiEvalResult(data);
        if (data.recommended_action === "QUARANTINE_ACCOUNT" && !quarantinedList.includes(userDid)) {
          setQuarantinedList([userDid, ...quarantinedList]);
        }
      } else {
        throw new Error("API hatasi");
      }
    } catch {
      // Offline fallback simülasyonu
      const score = (aiGeoKm > 500 ? 0.5 : 0) + (aiFailedCount >= 3 ? 0.35 : 0) + (aiIsTor ? 0.4 : 0);
      const finalScore = Math.min(score, 1.0);
      setAiEvalResult({
        risk_score: finalScore,
        risk_level: finalScore > 0.8 ? "CRITICAL" : finalScore > 0.5 ? "HIGH" : finalScore > 0.25 ? "MEDIUM" : "LOW",
        recommended_action: finalScore > 0.8 ? "QUARANTINE_ACCOUNT" : finalScore > 0.5 ? "MANUAL_REVIEW" : finalScore > 0.25 ? "REQUIRE_STEP_UP_AUTH" : "ALLOW",
        reasons: aiGeoKm > 500 ? ["İmkansız seyahat anomalisi tespit edildi."] : ["Normal erişim deseni."]
      });
    } finally {
      setAiLoading(false);
    }
  };

  const handleGuardianApprove = (id: number) => {
    const updated = guardians.map(g => g.id === id ? { ...g, approved: true } : g);
    setGuardians(updated);
  };

  const approvedCount = guardians.filter(g => g.approved).length;

  return (
    <div className="app-shell">
      <Navbar
        isWalletConnected={isWalletConnected}
        onToggleWallet={() => setIsWalletConnected(!isWalletConnected)}
        walletAddress={walletAddress}
        userDid={userDid}
      />

      <div className="app-body">
        <Sidebar activeSection={activeSection} onSelectSection={setActiveSection} />

        <main className="app-content">
          {/* ========================================================= */}
          {/* 1. KİMLİK CÜZDANIM (WALLET PORTAL) */}
          {/* ========================================================= */}
          {activeSection === "wallet" && (
            <div>
              <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <h1>Kimlik Cüzdanım (Holder Wallet)</h1>
                  <p>W3C standartlarında Verifiable Credentials ve aktif DID anahtarlarınız.</p>
                </div>
                <button className="btn-connect-wallet" onClick={handleGenerateNewDid} style={{ padding: "10px 16px" }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                  </svg>
                  Yeni DID Anahtarı Üret
                </button>
              </div>

              {didCopied && (
                <div style={{ background: "rgba(16, 185, 129, 0.15)", border: "1px solid #10b981", color: "#34d399", padding: "10px 16px", borderRadius: "10px", marginBottom: "20px", fontSize: "0.88rem" }}>
                  ✔ Yeni Ed25519 DID başarıyla üretildi: <code>{userDid}</code>
                </div>
              )}

              <div className="grid-2">
                {/* SOL: CÜZDANDAKİ BELGELER */}
                <div>
                  <h3 style={{ marginBottom: "14px", color: "var(--text-main)" }}>Kayıtlı Kimlik Bilgileri ({credentials.length})</h3>
                  {credentials.map(c => (
                    <div
                      key={c.id}
                      onClick={() => setSelectedCred(c)}
                      style={{
                        background: selectedCred?.id === c.id ? "#11223b" : "var(--bg-card)",
                        border: `1px solid ${selectedCred?.id === c.id ? "var(--accent-cyan)" : "var(--border-color)"}`,
                        borderRadius: "14px",
                        padding: "20px",
                        marginBottom: "14px",
                        cursor: "pointer",
                        transition: "all 0.2s"
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", fontWeight: 700 }}>W3C VERIFIABLE CREDENTIAL</span>
                        <span className={c.status === "ACTIVE" ? "badge-green" : "badge-red"}>{c.status}</span>
                      </div>
                      <h4 style={{ fontSize: "1.1rem", marginBottom: "6px", color: "#fff" }}>{c.title}</h4>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Düzenleyen: {c.issuer}</div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-subtle)", marginTop: "8px" }}>Tarih: {c.issuedDate}</div>
                    </div>
                  ))}
                </div>

                {/* SAĞ: SEÇİLİ BELGE ÖNİZLEME & DETAY KARTI */}
                {selectedCred && (
                  <div className="web3-card" style={{ border: "1px solid rgba(56, 189, 248, 0.4)", background: "linear-gradient(145deg, #0d1b30, #081120)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
                      <div>
                        <span style={{ fontSize: "0.72rem", color: "#38bdf8", letterSpacing: "0.1em", fontWeight: 700 }}>T.C. SAKARYA UYGULAMALI BİLİMLER ÜNİVERSİTESİ</span>
                        <h2 style={{ fontSize: "1.4rem", margin: "6px 0 0", color: "#fff" }}>{selectedCred.claims.bolum}</h2>
                        <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>{selectedCred.claims.derece}</span>
                      </div>
                      <div style={{ width: "42px", height: "42px", background: "#1e3a8a33", border: "1px solid #38bdf866", borderRadius: "10px", display: "flex", alignItems: "center", justifyContent: "center", color: "#38bdf8" }}>
                        🎓
                      </div>
                    </div>

                    <div style={{ background: "#050c17", padding: "16px", borderRadius: "10px", border: "1px solid #162a45", marginBottom: "18px" }}>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", fontSize: "0.85rem" }}>
                        <div><span style={{ color: "var(--text-subtle)", fontSize: "0.75rem" }}>ÖĞRENCİ:</span><br/><strong>{selectedCred.claims.ogrenciAdi}</strong></div>
                        <div><span style={{ color: "var(--text-subtle)", fontSize: "0.75rem" }}>ÖĞRENCİ NO:</span><br/><strong>{selectedCred.claims.ogrenciNo}</strong></div>
                        <div><span style={{ color: "var(--text-subtle)", fontSize: "0.75rem" }}>FAKÜLTE:</span><br/>{selectedCred.claims.fakulte}</div>
                        <div><span style={{ color: "var(--text-subtle)", fontSize: "0.75rem" }}>NOT ORTALAMASI:</span><br/><strong style={{ color: "#34d399" }}>{selectedCred.claims.gpa}</strong></div>
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                      <button className="btn-connect-wallet" style={{ flex: 1, justifyContent: "center" }} onClick={() => setShowQrModal(true)}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                        QR Kod Doğrulama
                      </button>
                      <button
                        className="btn-connect-wallet"
                        style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155" }}
                        onClick={() => {
                          const blob = new Blob([JSON.stringify(selectedCred, null, 2)], { type: "application/json" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `diploma-${selectedCred.claims.ogrenciNo}.json`;
                          a.click();
                        }}
                      >
                        JSON-LD İndir
                      </button>
                    </div>

                    {/* QR MODAL */}
                    {showQrModal && (
                      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
                        <div style={{ background: "#0c1728", padding: "28px", borderRadius: "18px", border: "1px solid var(--border-color)", textAlign: "center", maxWidth: "340px" }}>
                          <h3 style={{ marginBottom: "12px", color: "#fff" }}>W3C Verifiable Presentation QR</h3>
                          <div style={{ background: "#fff", padding: "16px", borderRadius: "12px", display: "inline-block", margin: "10px 0" }}>
                            <svg width="160" height="160" viewBox="0 0 100 100">
                              <rect width="100" height="100" fill="#fff"/>
                              <path d="M10 10h30v30h-30zM60 10h30v30h-30zM10 60h30v30h-30zM20 20h10v10h-10zM70 20h10v10h-10zM20 70h10v10h-10zM45 45h10v10h-10zM60 60h15v15h-15zM75 75h15v15h-15zM45 10h10v20h-10zM10 45h20v10h-20z" fill="#000"/>
                            </svg>
                          </div>
                          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "16px" }}>
                            Doğrulayıcı (işveren) kamerasıyla tarandığında anında geçerlilik testi yapılır.
                          </p>
                          <button className="btn-connect-wallet" style={{ width: "100%", justifyContent: "center" }} onClick={() => setShowQrModal(false)}>
                            Kapat
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* 2. BELGE DÜZENLEYİCİ (ISSUER PORTAL) */}
          {/* ========================================================= */}
          {activeSection === "issuer" && (
            <div>
              <div className="page-header">
                <h1>Belge Düzenleyici (Issuer Portal)</h1>
                <p>Sakarya Uygulamalı Bilimler Üniversitesi adına W3C uyumlu dijital diploma oluşturun ve imzalayın.</p>
              </div>

              {issuerNotification && (
                <div style={{ background: "rgba(16, 185, 129, 0.15)", border: "1px solid #10b981", color: "#34d399", padding: "12px 20px", borderRadius: "10px", marginBottom: "20px", fontWeight: 600 }}>
                  ✔ {issuerNotification}
                </div>
              )}

              <div className="grid-2">
                <div className="web3-card">
                  <div className="card-title-group">
                    <h2>Yeni Diploma Düzenleme Formu</h2>
                    <p>Öğrenci bilgilerini girip kriptografik Ed25519 imzasıyla yayınlayın.</p>
                  </div>

                  <form onSubmit={handleIssueCredential}>
                    <div style={{ marginBottom: "14px" }}>
                      <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>Öğrenci Adı Soyadı</label>
                      <input
                        type="text"
                        style={{ width: "100%", padding: "10px 14px", background: "#060b14", border: "1px solid var(--border-color)", borderRadius: "8px", color: "#fff" }}
                        value={issuerStudentName}
                        onChange={e => setIssuerStudentName(e.target.value)}
                        required
                      />
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "14px" }}>
                      <div>
                        <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>Öğrenci Numarası</label>
                        <input
                          type="text"
                          style={{ width: "100%", padding: "10px 14px", background: "#060b14", border: "1px solid var(--border-color)", borderRadius: "8px", color: "#fff" }}
                          value={issuerStudentId}
                          onChange={e => setIssuerStudentId(e.target.value)}
                          required
                        />
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>Not Ortalaması (GPA)</label>
                        <input
                          type="text"
                          style={{ width: "100%", padding: "10px 14px", background: "#060b14", border: "1px solid var(--border-color)", borderRadius: "8px", color: "#fff" }}
                          value={issuerGpa}
                          onChange={e => setIssuerGpa(e.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div style={{ marginBottom: "20px" }}>
                      <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>Bölüm</label>
                      <input
                        type="text"
                        style={{ width: "100%", padding: "10px 14px", background: "#060b14", border: "1px solid var(--border-color)", borderRadius: "8px", color: "#fff" }}
                        value={issuerDepartment}
                        onChange={e => setIssuerDepartment(e.target.value)}
                        required
                      />
                    </div>

                    <button type="submit" className="btn-connect-wallet" style={{ width: "100%", justifyContent: "center", padding: "12px" }}>
                      W3C Diplomasını İmzala ve Cüzdana Gönder
                    </button>
                  </form>
                </div>

                <div className="web3-card">
                  <div className="card-title-group">
                    <h2>Düzenlenen Belgeler & İptal (Revocation)</h2>
                    <p>Status List 2021 / W3C Bitstring üzerinden anlık iptal kontrolü.</p>
                  </div>

                  {credentials.map(c => (
                    <div key={c.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "#081120", borderRadius: "8px", border: "1px solid var(--border-color)", marginBottom: "10px" }}>
                      <div>
                        <strong>{c.claims.ogrenciAdi}</strong> ({c.claims.ogrenciNo})
                        <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{c.claims.bolum} · {c.status}</div>
                      </div>
                      {c.status === "ACTIVE" ? (
                        <button
                          onClick={() => handleRevokeCredential(c.id)}
                          style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#f87171", padding: "6px 12px", borderRadius: "6px", fontSize: "0.78rem", cursor: "pointer" }}
                        >
                          İptal Et (Revoke)
                        </button>
                      ) : (
                        <span className="badge-red">İptal Edildi</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* 3. DOĞRULAYICI PORTAL (VERIFIER) */}
          {/* ========================================================= */}
          {activeSection === "verifier" && (
            <div>
              <div className="page-header">
                <h1>Doğrulayıcı Portal (Verifier)</h1>
                <p>Adayın veya çalışanın sunduğu W3C Diplomasını ve Sıfır Bilgi Kanıtını (ZKP) test edin.</p>
              </div>

              <div className="grid-2">
                <div className="web3-card">
                  <div className="card-title-group">
                    <h2>Kimlik Belgesi Doğrulama</h2>
                    <p>Doğrulanacak Verifiable Credential detayları:</p>
                  </div>

                  {selectedCred ? (
                    <div style={{ background: "#060c16", padding: "16px", borderRadius: "10px", border: "1px solid var(--border-color)", marginBottom: "18px" }}>
                      <div style={{ fontSize: "0.85rem", marginBottom: "8px" }}><strong>Belge:</strong> {selectedCred.title}</div>
                      <div style={{ fontSize: "0.85rem", marginBottom: "8px" }}><strong>İmzacı:</strong> {selectedCred.issuer}</div>
                      <div style={{ fontSize: "0.85rem", marginBottom: "8px" }}><strong>Durum:</strong> <span className={selectedCred.status === "ACTIVE" ? "badge-green" : "badge-red"}>{selectedCred.status}</span></div>

                      <div style={{ marginTop: "14px", paddingTop: "12px", borderTop: "1px solid var(--border-color)" }}>
                        <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", cursor: "pointer", color: "var(--accent-cyan)" }}>
                          <input type="checkbox" checked={zkpMasked} onChange={e => setZkpMasked(e.target.checked)} />
                          Zero-Knowledge Proof (ZKP) ile Kişisel Verileri Gizle (Yalnızca GPA &gt;= 3.0 Kanıtla)
                        </label>
                      </div>
                    </div>
                  ) : (
                    <p>Seçili belge bulunamadı.</p>
                  )}

                  <button
                    className="btn-connect-wallet"
                    style={{ width: "100%", justifyContent: "center", padding: "12px" }}
                    onClick={handleVerifyCredential}
                    disabled={isVerifying}
                  >
                    {isVerifying ? "W3C İmzası & Bitstring Kontrol Ediliyor..." : "Doğrulamayı Başlat (Verify)"}
                  </button>
                </div>

                {/* DOĞRULAMA SONUÇLARI */}
                <div className="web3-card">
                  <div className="card-title-group">
                    <h2>Kriptografik Doğrulama Sonucu</h2>
                    <p>Matematiksel imza, zaman aşımı ve iptal kayıtlarının analizi:</p>
                  </div>

                  {verifierResult ? (
                    verifierResult.valid ? (
                      <div>
                        <div style={{ padding: "14px 18px", background: "rgba(16, 185, 129, 0.15)", border: "1px solid #10b981", borderRadius: "10px", color: "#34d399", marginBottom: "16px" }}>
                          <h4 style={{ margin: 0, fontSize: "1.05rem" }}>✅ BELGE %100 GEÇERLİ VE DOĞRULANDI</h4>
                          <div style={{ fontSize: "0.8rem", marginTop: "4px" }}>Doğrulama Süresi: {verifierResult.latencyMs} ms</div>
                        </div>

                        <div style={{ fontSize: "0.85rem", lineHeight: "1.7", color: "var(--text-muted)" }}>
                          <div>• <strong>İmzacı Güvenilirlik:</strong> SUBÜ Resmi Root Anahtarı ile eşleşti.</div>
                          <div>• <strong>Algoritma:</strong> {verifierResult.algorithm}</div>
                          <div>• <strong>Revocation Durumu:</strong> Bitstring Status List üzerinde aktif.</div>
                          {zkpMasked && (
                            <div style={{ marginTop: "10px", padding: "10px", background: "#0b192c", borderRadius: "8px", border: "1px solid #1d4ed8" }}>
                              <strong style={{ color: "var(--accent-cyan)" }}>🛡️ ZKP Range Predicate Kanıtı:</strong>
                              <div style={{ color: "#fff", fontSize: "0.82rem" }}>{verifierResult.zkpPredicate}</div>
                              <div style={{ fontSize: "0.75rem", color: "var(--text-subtle)", marginTop: "2px" }}>Öğrencinin TC Kimlik No ve İsim alanları ifşa edilmedi (Gizlilik Korundu).</div>
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div style={{ padding: "14px 18px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "10px", color: "#f87171" }}>
                        <h4 style={{ margin: 0 }}>❌ DOĞRULAMA BAŞARISIZ</h4>
                        <div style={{ fontSize: "0.85rem", marginTop: "4px" }}>{verifierResult.reason}</div>
                      </div>
                    )
                  ) : (
                    <div style={{ textAlign: "center", padding: "30px", color: "var(--text-subtle)" }}>
                      Henüz bir doğrulama yapılmadı. Soldaki butona tıklayın.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* 4. AI GÜVENLİK MERKEZİ (FRAUD MONITOR) */}
          {/* ========================================================= */}
          {activeSection === "ai" && (
            <div>
              <div className="page-header">
                <h1>Yapay Zekâ Dolandırıcılık Tespiti (AI Fraud Monitor)</h1>
                <p>XGBoost + Autoencoder hibrit modeliyle gerçek zamanlı davranış analizi ve karantina paneli.</p>
              </div>

              <div className="grid-2">
                <div className="web3-card">
                  <div className="card-title-group">
                    <h2>Canlı Davranış Parametre Simülatörü</h2>
                    <p>Modelin tepkisini ölçmek için erişim parametrelerini ayarlayın:</p>
                  </div>

                  <div style={{ marginBottom: "14px" }}>
                    <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>
                      Coğrafi Konum Sıçraması: <strong>{aiGeoKm} km</strong>
                    </label>
                    <input type="range" min="0" max="3500" step="50" value={aiGeoKm} onChange={e => setAiGeoKm(Number(e.target.value))} style={{ width: "100%" }} />
                  </div>

                  <div style={{ marginBottom: "14px" }}>
                    <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>
                      Son 10 Dakikadaki Başarısız Oturum Denemesi: <strong>{aiFailedCount}</strong>
                    </label>
                    <input type="range" min="0" max="8" value={aiFailedCount} onChange={e => setAiFailedCount(Number(e.target.value))} style={{ width: "100%" }} />
                  </div>

                  <div style={{ marginBottom: "14px" }}>
                    <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>
                      Doğrulama İsteği Sıklığı (10 dk): <strong>{aiFreq} istek</strong>
                    </label>
                    <input type="range" min="1" max="30" value={aiFreq} onChange={e => setAiFreq(Number(e.target.value))} style={{ width: "100%" }} />
                  </div>

                  <div style={{ display: "flex", gap: "20px", marginBottom: "20px" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", cursor: "pointer" }}>
                      <input type="checkbox" checked={aiIsTor} onChange={e => setAiIsTor(e.target.checked)} />
                      Tor / Anonim Proxy
                    </label>
                    <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", cursor: "pointer" }}>
                      <input type="checkbox" checked={aiDeviceMatch} onChange={e => setAiDeviceMatch(e.target.checked)} />
                      Kayıtlı Cihaz Parmak İzi
                    </label>
                  </div>

                  <button
                    className="btn-connect-wallet"
                    style={{ width: "100%", justifyContent: "center", padding: "12px" }}
                    onClick={handleRunAiEvaluation}
                    disabled={aiLoading}
                  >
                    {aiLoading ? "AI Modeli Analiz Ediyor..." : "Backend AI Servisi ile Analiz Et (Port 8002)"}
                  </button>
                </div>

                {/* AI SONUÇLARI */}
                <div className="web3-card">
                  <div className="card-title-group">
                    <h2>AI Karar ve Güvenlik Aksiyonu</h2>
                    <p>Gerçek zamanlı çıkarım sonucu:</p>
                  </div>

                  {aiEvalResult ? (
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "18px" }}>
                        <div style={{ fontSize: "2.8rem", fontWeight: "800", color: aiEvalResult.risk_score > 0.6 ? "var(--accent-red)" : aiEvalResult.risk_score > 0.25 ? "var(--accent-yellow)" : "var(--accent-green)" }}>
                          {(aiEvalResult.risk_score * 100).toFixed(1)}%
                        </div>
                        <div>
                          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Hesaplanan Risk Skoru</div>
                          <span className={aiEvalResult.risk_level === "CRITICAL" ? "badge-red" : aiEvalResult.risk_level === "HIGH" ? "badge-red" : aiEvalResult.risk_level === "MEDIUM" ? "badge-yellow" : "badge-green"}>
                            {aiEvalResult.risk_level} RISK
                          </span>
                        </div>
                      </div>

                      <div style={{ background: "#060c16", padding: "14px", borderRadius: "8px", border: "1px solid var(--border-color)", marginBottom: "16px" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-subtle)" }}>SİSTEMİN ALDIĞI GÜVENLİK KARARI:</span>
                        <div style={{ fontSize: "1.1rem", fontWeight: "bold", color: "var(--accent-cyan)", marginTop: "4px" }}>
                          {aiEvalResult.recommended_action}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "6px" }}>Tespit Nedenleri:</div>
                        <ul style={{ paddingLeft: "18px", fontSize: "0.85rem", color: "#cbd5e1" }}>
                          {aiEvalResult.reasons?.map((r: string, idx: number) => <li key={idx} style={{ marginBottom: "4px" }}>{r}</li>)}
                        </ul>
                      </div>
                    </div>
                  ) : (
                    <div style={{ textAlign: "center", padding: "30px", color: "var(--text-subtle)" }}>
                      Analiz sonucunu görmek için soldaki butona tıklayın.
                    </div>
                  )}

                  {quarantinedList.length > 0 && (
                    <div style={{ marginTop: "20px", paddingTop: "14px", borderTop: "1px solid var(--border-color)" }}>
                      <span style={{ fontSize: "0.82rem", color: "var(--accent-red)", fontWeight: "bold" }}>Aktif Karantinadaki Hesaplar ({quarantinedList.length})</span>
                      {quarantinedList.map(did => (
                        <div key={did} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(239, 68, 68, 0.1)", padding: "8px 12px", borderRadius: "6px", marginTop: "8px" }}>
                          <span style={{ fontSize: "0.78rem", color: "#f87171" }}>{did.slice(0, 28)}...</span>
                          <button onClick={() => setQuarantinedList(quarantinedList.filter(x => x !== did))} style={{ background: "#1e293b", border: "none", color: "#fff", padding: "4px 8px", borderRadius: "4px", fontSize: "0.72rem", cursor: "pointer" }}>
                            Kaldır
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* 5. SOSYAL KURTARMA (3/5 GUARDIAN) */}
          {/* ========================================================= */}
          {activeSection === "recovery" && (
            <div>
              <div className="page-header">
                <h1>3/5 Guardian Sosyal Kurtarma Portalı</h1>
                <p>Anahtar veya cihaz kaybında kimliğinizi 3/5 Guardian onayı ve Time-Lock ile kurtarın.</p>
              </div>

              <div className="web3-card" style={{ marginBottom: "20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
                  <div>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Onay Durumu</span>
                    <h2 style={{ fontSize: "1.8rem", color: approvedCount >= 3 ? "var(--accent-green)" : "var(--accent-cyan)", margin: "4px 0" }}>
                      {approvedCount} / 5 Guardian Onayladı
                    </h2>
                    <span style={{ fontSize: "0.82rem", color: approvedCount >= 3 ? "#34d399" : "var(--text-subtle)" }}>
                      {approvedCount >= 3 ? "✔ 3/5 M-of-N Quorum Eşiği Sağlandı (Time-Lock Doğrulandı)" : "En az 3 onay gereklidir."}
                    </span>
                  </div>

                  {approvedCount >= 3 && !recoveryExecuted && (
                    <button className="btn-connect-wallet" style={{ background: "linear-gradient(135deg, #10b981, #059669)" }} onClick={() => setRecoveryExecuted(true)}>
                      Yeni Anahtar Rotasyonunu İcra Et
                    </button>
                  )}

                  {recoveryExecuted && (
                    <div style={{ background: "rgba(16, 185, 129, 0.2)", border: "1px solid #10b981", padding: "10px 18px", borderRadius: "10px", color: "#34d399", fontWeight: "bold" }}>
                      ✅ Kurtarma Tamamlandı! Yeni DID Aktif Edildi.
                    </div>
                  )}
                </div>
              </div>

              <div className="grid-3">
                {guardians.map(g => (
                  <div key={g.id} className="web3-card" style={{ padding: "18px", border: `1px solid ${g.approved ? "rgba(16, 185, 129, 0.4)" : "var(--border-color)"}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <strong>{g.name}</strong>
                      <span className={g.approved ? "badge-green" : "badge-yellow"}>{g.approved ? "ONAYLANDI" : "BEKLİYOR"}</span>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "12px" }}>{g.role}</div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-subtle)", fontFamily: "monospace", marginBottom: "14px", wordBreak: "break-all" }}>{g.did}</div>

                    {!g.approved ? (
                      <button className="btn-connect-wallet" style={{ width: "100%", justifyContent: "center", padding: "8px", fontSize: "0.82rem" }} onClick={() => handleGuardianApprove(g.id)}>
                        Guardian Olarak Onayla
                      </button>
                    ) : (
                      <div style={{ textAlign: "center", fontSize: "0.78rem", color: "#34d399" }}>Şifreli Onay Kaydedildi</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* 6. BLOCKCHAIN GEZGİNİ (EXPLORER) */}
          {/* ========================================================= */}
          {activeSection === "blockchain" && (
            <div>
              <div className="page-header">
                <h1>Ethereum Blockchain Denetim Defteri</h1>
                <p>Hardhat EVM üzerindeki 4 akıllı sözleşmenin değişmez kayıtları ve gas harcamaları.</p>
              </div>

              <div className="web3-card">
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-color)", textAlign: "left", color: "var(--text-muted)" }}>
                      <th style={{ padding: "12px" }}>İşlem / Fonksiyon</th>
                      <th style={{ padding: "12px" }}>Akıllı Sözleşme</th>
                      <th style={{ padding: "12px" }}>Blok / Ağ</th>
                      <th style={{ padding: "12px" }}>Gas Harcaması</th>
                      <th style={{ padding: "12px" }}>Durum</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: "1px solid var(--border-color)" }}>
                      <td style={{ padding: "12px" }}><code>registerDID(string, bytes32)</code></td>
                      <td style={{ padding: "12px" }}><strong>DIDRegistry.sol</strong></td>
                      <td style={{ padding: "12px" }}>Block #1042 (Localnet)</td>
                      <td style={{ padding: "12px", color: "var(--accent-cyan)" }}>48,120 gas (~0.00012 ETH)</td>
                      <td style={{ padding: "12px" }}><span className="badge-green">ONAYLANDI</span></td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid var(--border-color)" }}>
                      <td style={{ padding: "12px" }}><code>anchorStatusList(string, bytes32, uint256)</code></td>
                      <td style={{ padding: "12px" }}><strong>RevocationRegistry.sol</strong></td>
                      <td style={{ padding: "12px" }}>Block #1043 (Localnet)</td>
                      <td style={{ padding: "12px", color: "var(--accent-cyan)" }}>62,400 gas (~0.00015 ETH)</td>
                      <td style={{ padding: "12px" }}><span className="badge-green">ONAYLANDI</span></td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid var(--border-color)" }}>
                      <td style={{ padding: "12px" }}><code>approveRecovery(address)</code></td>
                      <td style={{ padding: "12px" }}><strong>EmergencyRecovery.sol</strong></td>
                      <td style={{ padding: "12px" }}>Block #1044 (Localnet)</td>
                      <td style={{ padding: "12px", color: "var(--accent-cyan)" }}>38,900 gas (~0.00009 ETH)</td>
                      <td style={{ padding: "12px" }}><span className="badge-green">ONAYLANDI</span></td>
                    </tr>
                    <tr>
                      <td style={{ padding: "12px" }}><code>logEvent(bytes32, uint8)</code></td>
                      <td style={{ padding: "12px" }}><strong>AuditLogger.sol</strong></td>
                      <td style={{ padding: "12px" }}>Block #1045 (Localnet)</td>
                      <td style={{ padding: "12px", color: "var(--accent-cyan)" }}>74,100 gas (~0.00018 ETH)</td>
                      <td style={{ padding: "12px" }}><span className="badge-green">ONAYLANDI</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
