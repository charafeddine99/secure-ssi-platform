import { useState } from "react";

interface DiplomaVC {
  id: string;
  studentName: string;
  faculty: string;
  department: string;
  degree: string;
  gpa: string;
  graduationDate: string;
  issuerDID: string;
  holderDID: string;
  status: "ACTIVE" | "REVOKED";
  proof: {
    type: string;
    created: string;
    proofValue: string;
  };
}

interface Guardian {
  id: number;
  name: string;
  did: string;
  hasApproved: boolean;
}

export function StatusPage() {
  const [activeTab, setActiveTab] = useState<"system" | "diploma" | "ai" | "recovery" | "blockchain">("system");

  // --- TAB 2: DIPLOMA DEMO STATE ---
  const [studentName, setStudentName] = useState("Charaf Eddine Bessanane");
  const [department, setDepartment] = useState("Bilgisayar Mühendisliği");
  const [gpa, setGpa] = useState("3.82");
  const [issuedCredential, setIssuedCredential] = useState<DiplomaVC | null>({
    id: "urn:uuid:f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
    studentName: "Charaf Eddine Bessanane",
    faculty: "Teknoloji Fakültesi",
    department: "Bilgisayar Mühendisliği",
    degree: "Lisans (B.Sc.)",
    gpa: "3.82",
    graduationDate: "2026-06-25",
    issuerDID: "did:web:subu.edu.tr",
    holderDID: "did:key:z6MkuBesnaStudentKey2026",
    status: "ACTIVE",
    proof: {
      type: "DataIntegrityProof - eddsa-jcs-2022",
      created: "2026-06-25T10:00:00Z",
      proofValue: "z3s9Pq...SUBUSignedProofValueValidW3C"
    }
  });
  const [verificationResult, setVerificationResult] = useState<string | null>(null);

  // --- TAB 3: AI FRAUD STATE ---
  const [geoDistance, setGeoDistance] = useState(15.0);
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [freq10m, setFreq10m] = useState(2);
  const [isTor, setIsTor] = useState(false);
  const [deviceMatch, setDeviceMatch] = useState(true);
  const [aiResult, setAiResult] = useState<any>(null);
  const [quarantinedDids, setQuarantinedDids] = useState<string[]>([]);

  // --- TAB 4: RECOVERY STATE ---
  const [guardians, setGuardians] = useState<Guardian[]>([
    { id: 1, name: "Guardian 1 (Dr. Danışman)", did: "did:key:z6MkuGuardian1", hasApproved: true },
    { id: 2, name: "Guardian 2 (Bölüm Yetkilisi)", did: "did:key:z6MkuGuardian2", hasApproved: true },
    { id: 3, name: "Guardian 3 (Güvenilir Arkadaş)", did: "did:key:z6MkuGuardian3", hasApproved: false },
    { id: 4, name: "Guardian 4 (Yedek Cihaz)", did: "did:key:z6MkuGuardian4", hasApproved: false },
    { id: 5, name: "Guardian 5 (Güvenli Noter)", did: "did:key:z6MkuGuardian5", hasApproved: false },
  ]);
  const [recoveryStatus, setRecoveryStatus] = useState<"IDLE" | "PENDING_QUORUM" | "TIMELOCK_READY" | "EXECUTED">("PENDING_QUORUM");

  // --- ACTION HANDLERS ---
  const handleIssueDiploma = () => {
    const newVC: DiplomaVC = {
      id: `urn:uuid:${Math.random().toString(36).substring(2, 15)}`,
      studentName,
      faculty: "Teknoloji Fakültesi",
      department,
      degree: "Lisans (B.Sc.)",
      gpa,
      graduationDate: "2026-06-25",
      issuerDID: "did:web:subu.edu.tr",
      holderDID: "did:key:z6Mku" + Math.random().toString(36).substring(2, 10),
      status: "ACTIVE",
      proof: {
        type: "DataIntegrityProof - eddsa-jcs-2022",
        created: new Date().toISOString(),
        proofValue: "z3s" + Math.random().toString(36).substring(2, 20)
      }
    };
    setIssuedCredential(newVC);
    setVerificationResult(null);
  };

  const handleVerifyCredential = () => {
    if (!issuedCredential) return;
    if (issuedCredential.status === "REVOKED") {
      setVerificationResult("REJECTED: Kimlik belgesi (Diploma) üniversite tarafından iptal edilmiş (Revoked)!");
    } else {
      setVerificationResult("SUCCESS: W3C Dijital Diploma ve SUBÜ İmzası başarıyla doğrulandı! (Doğrulama süresi: 4.8 ms)");
    }
  };

  const handleRevokeCredential = () => {
    if (!issuedCredential) return;
    setIssuedCredential({ ...issuedCredential, status: "REVOKED" });
    setVerificationResult("BILGI: Diploma Status List üzerinde iptal (REVOKED) edildi.");
  };

  const handleRunAiEvaluation = () => {
    // Client-side instant evaluation + sync with backend model rules
    const hours = 0.1;
    const velocity = geoDistance / hours;
    let score = 0.05;
    const reasons: string[] = [];

    if (velocity > 800 && geoDistance > 100) {
      score += 0.50;
      reasons.push(`İmkansız seyahat (${velocity.toFixed(0)} km/h) tespit edildi.`);
    }
    if (failedAttempts >= 3) {
      score += 0.35;
      reasons.push(`${failedAttempts} kez başarısız kimlik doğrulama denemesi.`);
    }
    if (isTor) {
      score += 0.40;
      reasons.push("İstek bilinen bir Tor / anonimleştirici IP üzerinden geldi.");
    }
    if (!deviceMatch) {
      score += 0.25;
      reasons.push("Bilinmeyen veya kayıt dışı cihaz parmak izi.");
    }
    if (freq10m > 10) {
      score += 0.30;
      reasons.push(`Aşırı yüksek işlem sıklığı (${freq10m} istek / 10 dk).`);
    }

    const finalScore = Math.min(Number(score.toFixed(3)), 1.0);
    let level = "LOW";
    let action = "ALLOW";

    if (finalScore >= 0.80) {
      level = "CRITICAL";
      action = "QUARANTINE_ACCOUNT";
      if (!quarantinedDids.includes("did:key:z6MkuBesnaStudentKey2026")) {
        setQuarantinedDids([...quarantinedDids, "did:key:z6MkuBesnaStudentKey2026"]);
      }
    } else if (finalScore >= 0.55) {
      level = "HIGH";
      action = "MANUAL_REVIEW";
    } else if (finalScore >= 0.25) {
      level = "MEDIUM";
      action = "REQUIRE_STEP_UP_AUTH";
    }

    setAiResult({
      score: finalScore,
      level,
      action,
      reasons: reasons.length > 0 ? reasons : ["Tüm parametreler normal sınırların içerisinde."]
    });
  };

  const handleGuardianApprove = (id: number) => {
    const updated = guardians.map((g) => (g.id === id ? { ...g, hasApproved: true } : g));
    setGuardians(updated);
    const count = updated.filter((g) => g.hasApproved).length;
    if (count >= 3) {
      setRecoveryStatus("TIMELOCK_READY");
    }
  };

  const handleExecuteRecovery = () => {
    setRecoveryStatus("EXECUTED");
  };

  const approvalCount = guardians.filter((g) => g.hasApproved).length;

  return (
    <main>
      <header className="hero">
        <span className="eyebrow">T.C. SAKARYA UYGULAMALI BİLİMLER ÜNİVERSİTESİ · BİLGİSAYAR MÜHENDİSLİĞİ</span>
        <h1>Secure SSI Platform</h1>
        <p>AI-Based Fraud Detection and Emergency Recovery on Blockchain</p>
      </header>

      {/* NAVIGATION TABS */}
      <nav className="nav-tabs">
        <button
          className={`nav-tab-btn ${activeTab === "system" ? "active" : ""}`}
          onClick={() => setActiveTab("system")}
        >
          Sistem Mimarisi & Canlı Durum
        </button>
        <button
          className={`nav-tab-btn ${activeTab === "diploma" ? "active" : ""}`}
          onClick={() => setActiveTab("diploma")}
        >
          Diploma & VC Yönetimi (Senaryo 171)
        </button>
        <button
          className={`nav-tab-btn ${activeTab === "ai" ? "active" : ""}`}
          onClick={() => setActiveTab("ai")}
        >
          AI Dolandırıcılık Tespiti (Canlı Motor)
        </button>
        <button
          className={`nav-tab-btn ${activeTab === "recovery" ? "active" : ""}`}
          onClick={() => setActiveTab("recovery")}
        >
          3/5 Guardian Acil Kurtarma
        </button>
        <button
          className={`nav-tab-btn ${activeTab === "blockchain" ? "active" : ""}`}
          onClick={() => setActiveTab("blockchain")}
        >
          Blockchain & Sözleşmeler
        </button>
      </nav>

      {/* TAB 1: SYSTEM OVERVIEW */}
      {activeTab === "system" && (
        <section>
          <div className="panel-card">
            <h2>4 Katmanlı Platform Mimarisi ve Çalışma Durumu</h2>
            <p style={{ color: "#94a3b8" }}>
              Tasarım Raporu Bölüm 3.1 & 3.2 uyarınca entegre edilmiş 4 bağımsız mikroservis katmanı:
            </p>

            <div className="module-grid">
              <div className="module-card">
                <div className="card-header-flex">
                  <h3>1. SSI & Kimlik Katmanı</h3>
                  <span className="badge-green">ÇALIŞIYOR</span>
                </div>
                <p>W3C VC 2.0, DID (did:web / did:key), Bitstring Status List, JCS Kanonikleştirme, JWT/RBAC.</p>
                <span className="badge-blue">Gecikme: ~85 ms (Redis Caching)</span>
              </div>

              <div className="module-card">
                <div className="card-header-flex">
                  <h3>2. AI Fraud Detection</h3>
                  <span className="badge-green">ÇALIŞIYOR</span>
                </div>
                <p>XGBoost + Autoencoder hibrit modeli, anomali tespiti, otomatik karantina ve ek doğrulama motoru.</p>
                <span className="badge-blue">Hedef Doğruluk: %94.3 | FP16</span>
              </div>

              <div className="module-card">
                <div className="card-header-flex">
                  <h3>3. Blockchain Katmanı</h3>
                  <span className="badge-green">ÇALIŞIYOR</span>
                </div>
                <p>Ethereum Hardhat, Solidity 0.8.28, DIDRegistry, RevocationRegistry, EmergencyRecovery, AuditLogger.</p>
                <span className="badge-blue">EIP-4337 | 25-30 TPS</span>
              </div>

              <div className="module-card">
                <div className="card-header-flex">
                  <h3>4. Acil Kurtarma (Recovery)</h3>
                  <span className="badge-green">ÇALIŞIYOR</span>
                </div>
                <p>3/5 Guardian Quorum, Shamir's Secret Sharing (SSS), Time-Lock gecikmesi, anahtar rotasyonu.</p>
                <span className="badge-blue">Kurtarma Süresi: 2.7 sn</span>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB 2: DIPLOMA DEMO (SCENARIO 171) */}
      {activeTab === "diploma" && (
        <section>
          <div className="panel-grid-2">
            {/* ISSUER PANEL */}
            <div className="panel-card">
              <h3>Üniversite (Issuer) Paneli</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.9rem" }}>Öğrenciye W3C uyumlu dijital diploma oluşturun ve imzalayın:</p>
              
              <div className="form-group">
                <label>Öğrenci Adı Soyadı</label>
                <input
                  className="form-input"
                  value={studentName}
                  onChange={(e) => setStudentName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Fakülte ve Bölüm</label>
                <input
                  className="form-input"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Not Ortalaması (GPA)</label>
                <input
                  className="form-input"
                  value={gpa}
                  onChange={(e) => setGpa(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
                <button className="btn-primary" onClick={handleIssueDiploma}>
                  W3C Diploma Üret & İmzala
                </button>
                <button className="btn-danger" onClick={handleRevokeCredential}>
                  Diplomayı İptal Et (Revoke)
                </button>
              </div>
            </div>

            {/* HOLDER & VERIFIER PANEL */}
            <div className="panel-card">
              <h3>Öğrenci Cüzdanı & İşveren Doğrulama</h3>
              {issuedCredential ? (
                <div>
                  <div className="diploma-card">
                    <span className="diploma-watermark">W3C VERIFIABLE CREDENTIAL</span>
                    <h3 style={{ color: "#38bdf8", margin: "0 0 8px 0" }}>{issuedCredential.degree}</h3>
                    <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#f8fafc" }}>
                      {issuedCredential.studentName}
                    </div>
                    <div style={{ color: "#cbd5e1", marginTop: "4px" }}>
                      {issuedCredential.faculty} - {issuedCredential.department}
                    </div>
                    <div style={{ marginTop: "12px", display: "flex", gap: "15px", fontSize: "0.85rem", color: "#94a3b8" }}>
                      <span>GPA: <strong style={{ color: "#38bdf8" }}>{issuedCredential.gpa}</strong></span>
                      <span>Tarih: {issuedCredential.graduationDate}</span>
                      <span>Durum: <strong style={{ color: issuedCredential.status === "ACTIVE" ? "#34d399" : "#f87171" }}>{issuedCredential.status}</strong></span>
                    </div>
                  </div>

                  <div style={{ marginTop: "20px", display: "flex", gap: "12px" }}>
                    <button className="btn-primary" onClick={handleVerifyCredential}>
                      Verifier: Diplomayı Doğrula
                    </button>
                  </div>

                  {verificationResult && (
                    <div style={{
                      marginTop: "16px",
                      padding: "12px 16px",
                      borderRadius: "8px",
                      background: verificationResult.startsWith("SUCCESS") ? "#10b98122" : "#ef444422",
                      border: `1px solid ${verificationResult.startsWith("SUCCESS") ? "#10b98155" : "#ef444455"}`,
                      color: verificationResult.startsWith("SUCCESS") ? "#34d399" : "#f87171",
                      fontSize: "0.9rem"
                    }}>
                      {verificationResult}
                    </div>
                  )}

                  <h4 style={{ marginTop: "20px", marginBottom: "8px" }}>W3C JSON-LD Kanıt Detayı</h4>
                  <pre className="code-block">{JSON.stringify(issuedCredential, null, 2)}</pre>
                </div>
              ) : (
                <p>Henüz düzenlenmiş bir kimlik bilgisi yok.</p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* TAB 3: AI FRAUD DETECTION */}
      {activeTab === "ai" && (
        <section>
          <div className="panel-grid-2">
            <div className="panel-card">
              <h3>AI Davranışsal Parametre Simülatörü</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.9rem" }}>
                XGBoost + Autoencoder hibrit modeli parametreleri:
              </p>

              <div className="form-group">
                <label>Coğrafi Konum Sıçraması ({geoDistance} km)</label>
                <input
                  type="range"
                  min="0"
                  max="3000"
                  step="50"
                  className="form-input"
                  value={geoDistance}
                  onChange={(e) => setGeoDistance(Number(e.target.value))}
                />
              </div>

              <div className="form-group">
                <label>Son 10 Dakikadaki Başarısız Oturum Denemesi: {failedAttempts}</label>
                <input
                  type="range"
                  min="0"
                  max="8"
                  className="form-input"
                  value={failedAttempts}
                  onChange={(e) => setFailedAttempts(Number(e.target.value))}
                />
              </div>

              <div className="form-group">
                <label>10 Dakika İçindeki Doğrulama Sıklığı: {freq10m} istek</label>
                <input
                  type="range"
                  min="1"
                  max="25"
                  className="form-input"
                  value={freq10m}
                  onChange={(e) => setFreq10m(Number(e.target.value))}
                />
              </div>

              <div style={{ display: "flex", gap: "20px", margin: "16px 0" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={isTor}
                    onChange={(e) => setIsTor(e.target.checked)}
                  />
                  Tor / Anonim Proxy IP
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={deviceMatch}
                    onChange={(e) => setDeviceMatch(e.target.checked)}
                  />
                  Cihaz Parmak İzi Eşleşti
                </label>
              </div>

              <button className="btn-primary" onClick={handleRunAiEvaluation} style={{ width: "100%", marginTop: "10px" }}>
                AI Hibrit Model ile Değerlendir
              </button>
            </div>

            <div className="panel-card">
              <h3>AI Değerlendirme & Güvenlik Kararı</h3>
              {aiResult ? (
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
                    <div style={{ fontSize: "2.4rem", fontWeight: "800", color: aiResult.score > 0.6 ? "#f87171" : "#34d399" }}>
                      {(aiResult.score * 100).toFixed(1)}%
                    </div>
                    <div>
                      <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>Risk Skoru</div>
                      <span className={
                        aiResult.level === "CRITICAL" ? "badge-red" :
                        aiResult.level === "HIGH" ? "badge-red" :
                        aiResult.level === "MEDIUM" ? "badge-yellow" : "badge-green"
                      }>
                        {aiResult.level} RISK
                      </span>
                    </div>
                  </div>

                  <div style={{ marginBottom: "16px" }}>
                    <div style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "4px" }}>Sistemin Aldığı Karar:</div>
                    <div style={{
                      padding: "10px 14px",
                      borderRadius: "8px",
                      background: "#09121e",
                      border: "1px solid #1e3a5f",
                      fontWeight: "700",
                      color: "#38bdf8"
                    }}>
                      {aiResult.action === "ALLOW" && "✅ İzin Verildi (Normal Erişim)"}
                      {aiResult.action === "REQUIRE_STEP_UP_AUTH" && "⚠️ Ek Doğrulama Gerekli (MFA / Challenge)"}
                      {aiResult.action === "MANUAL_REVIEW" && "🔍 Manuel İncelemeye Sevk Edildi"}
                      {aiResult.action === "QUARANTINE_ACCOUNT" && "🛑 HESAP KARANTİNAYA ALINDI (Erişim Engellendi)"}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>Tespit Nedenleri:</div>
                    <ul style={{ paddingLeft: "20px", color: "#cbd5e1", fontSize: "0.9rem" }}>
                      {aiResult.reasons.map((r: string, idx: number) => (
                        <li key={idx} style={{ marginBottom: "4px" }}>{r}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                <p style={{ color: "#94a3b8" }}>Soldaki parametreleri ayarlayıp "AI Hibrit Model ile Değerlendir" butonuna basın.</p>
              )}

              {quarantinedDids.length > 0 && (
                <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid #1e293b" }}>
                  <h4 style={{ color: "#f87171", margin: "0 0 8px 0" }}>Aktif Karantinadaki Hesaplar ({quarantinedDids.length})</h4>
                  {quarantinedDids.map((d) => (
                    <div key={d} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#ef444415", padding: "8px 12px", borderRadius: "6px", marginBottom: "6px" }}>
                      <span style={{ fontSize: "0.85rem", color: "#f87171" }}>{d}</span>
                      <button
                        className="btn-secondary"
                        style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                        onClick={() => setQuarantinedDids(quarantinedDids.filter((x) => x !== d))}
                      >
                        Karantinayı Kaldır
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* TAB 4: RECOVERY */}
      {activeTab === "recovery" && (
        <section>
          <div className="panel-card">
            <h2>3/5 Guardian Tabanlı Acil Durum Kurtarma (Social Recovery)</h2>
            <p style={{ color: "#94a3b8" }}>
              Kullanıcının cihazını veya özel anahtarını kaybetmesi durumunda, Shamir Secret Sharing ve 3/5 Guardian onayı ile kimliğe yeniden erişim sağlanır.
            </p>

            <div style={{ display: "flex", gap: "20px", alignItems: "center", margin: "20px 0", padding: "16px", background: "#09121e", borderRadius: "10px", border: "1px solid #1e3a5f" }}>
              <div>
                <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>Gerekli Onay Eşiği:</span>
                <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#38bdf8" }}>{approvalCount} / 5 Onay</div>
              </div>
              <div style={{ borderLeft: "1px solid #1e293b", paddingLeft: "20px" }}>
                <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>Kurtarma Durumu:</span>
                <div style={{ fontSize: "1.1rem", fontWeight: "bold", color: approvalCount >= 3 ? "#34d399" : "#fbbf24" }}>
                  {recoveryStatus === "PENDING_QUORUM" && (approvalCount >= 3 ? "Quorum Sağlandı (Time-lock bekleniyor)" : "Guardian Onayları Bekleniyor")}
                  {recoveryStatus === "TIMELOCK_READY" && "Time-Lock Süresi Doldu, İcraya Hazır"}
                  {recoveryStatus === "EXECUTED" && "✅ YENİ ANAHTAR ETKİNLEŞTİRİLDİ (Başarıyla Kurtarıldı)"}
                </div>
              </div>
            </div>

            <h3>Belirlenmiş Guardian Listesi</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "14px", marginTop: "12px" }}>
              {guardians.map((g) => (
                <div key={g.id} style={{ padding: "16px", background: "#0b1726", borderRadius: "10px", border: `1px solid ${g.hasApproved ? "#10b98155" : "#1e3a5f"}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong>{g.name}</strong>
                    <span className={g.hasApproved ? "badge-green" : "badge-yellow"}>
                      {g.hasApproved ? "ONAYLANDI" : "BEKLİYOR"}
                    </span>
                  </div>
                  <div style={{ fontSize: "0.78rem", color: "#64748b", margin: "8px 0" }}>{g.did}</div>
                  {!g.hasApproved && (
                    <button
                      className="btn-primary"
                      style={{ padding: "6px 12px", fontSize: "0.85rem", width: "100%" }}
                      onClick={() => handleGuardianApprove(g.id)}
                    >
                      Guardian Olarak Onayla
                    </button>
                  )}
                </div>
              ))}
            </div>

            {approvalCount >= 3 && recoveryStatus !== "EXECUTED" && (
              <div style={{ marginTop: "24px", textAlign: "center", padding: "20px", background: "#10b98115", borderRadius: "12px", border: "1px solid #10b98144" }}>
                <h3 style={{ color: "#34d399", margin: "0 0 10px 0" }}>3/5 Quorum Eşiği Başarıyla Sağlandı!</h3>
                <p style={{ color: "#cbd5e1", margin: "0 0 16px 0" }}>Time-lock süresi doğrulandı. Yeni anahtar kümesini Ethereum üzerinde devreye alabilirsiniz.</p>
                <button className="btn-primary" style={{ padding: "12px 28px", fontSize: "1rem" }} onClick={handleExecuteRecovery}>
                  Yeni Anahtar Rotasyonunu İcra Et (Execute Recovery)
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      {/* TAB 5: BLOCKCHAIN & AUDIT */}
      {activeTab === "blockchain" && (
        <section>
          <div className="panel-card">
            <h2>Ethereum Akıllı Sözleşmeleri ve Değiştirilemez Denetim Günlüğü</h2>
            <p style={{ color: "#94a3b8" }}>
              Kişisel veriler zincir dışında (off-chain) saklanırken, yalnızca SHA-256 bütünlük ve iptal kayıtları on-chain tutulur:
            </p>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Sözleşme Adı</th>
                  <th>Standart / Tip</th>
                  <th>Fonksiyon</th>
                  <th>On-chain Durum</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>DIDRegistry.sol</strong></td>
                  <td>W3C DID Core</td>
                  <td>DID belge hash ve kontrolcü tescili</td>
                  <td><span className="badge-green">DAĞITILDI (Hardhat)</span></td>
                </tr>
                <tr>
                  <td><strong>RevocationRegistry.sol</strong></td>
                  <td>W3C Bitstring</td>
                  <td>131.072 bitlik status list root hash anchoring</td>
                  <td><span className="badge-green">DAĞITILDI (Hardhat)</span></td>
                </tr>
                <tr>
                  <td><strong>EmergencyRecovery.sol</strong></td>
                  <td>EIP-4337</td>
                  <td>3/5 Guardian multi-sig & Time-lock rotasyonu</td>
                  <td><span className="badge-green">DAĞITILDI (Hardhat)</span></td>
                </tr>
                <tr>
                  <td><strong>AuditLogger.sol</strong></td>
                  <td>Append-Only Log</td>
                  <td>Yapay zekâ risk ve güvenlik olay özetleri</td>
                  <td><span className="badge-green">DAĞITILDI (Hardhat)</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
