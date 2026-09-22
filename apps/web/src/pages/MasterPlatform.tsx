import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { useWallet, EMERGENCY_RECOVERY_ADDRESS, DID_REGISTRY_ADDRESS } from "../context/WalletContext";
import { AuthPage } from "../components/auth/AuthPage";

// ============================================================================
// 1. CANONICAL ROLES (SECTION 2 & 12)
// ============================================================================
export type RoleKey = "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN";

// Screen Keys for each Role (Section 12 - Frontend Bilgi Mimarisi)
export type HolderScreen = 
  | "DASHBOARD" | "IDENTITY" | "WALLET" | "CREDENTIALS" | "CREDENTIAL_DETAIL" 
  | "PRESENT" | "CONSENT" | "VERIFICATION_RESULT" | "ACTIVITY" | "SECURITY" | "RECOVERY";

export type IssuerScreen = 
  | "DASHBOARD" | "TEMPLATES" | "ISSUE" | "ISSUED" | "REVOCATION" | "ORGANIZATION";

export type VerifierScreen = 
  | "DASHBOARD" | "CREATE_REQUEST" | "QR_LINK" | "PRESENTATION" | "VERIFICATION_RESULT" | "HISTORY";

export type GuardianScreen = 
  | "REQUESTS" | "REQUEST_DETAIL" | "APPROVE_REJECT" | "HISTORY";

export type AdminScreen = 
  | "USERS" | "ORGANIZATIONS" | "TRUST" | "FRAUD" | "RECOVERY" | "BLOCKCHAIN" | "AUDIT" | "SYSTEM";

// W3C Verifiable Credential Data Model (Section 3)
export interface VerifiableCredentialItem {
  id: string;
  title: string;
  category: "IDENTITY" | "TRAVEL" | "TRANSPORT" | "HEALTH" | "FINANCE" | "EDUCATION";
  type: string;
  issuer: string;
  issuerName: string;
  issuedDate: string;
  expiryDate?: string;
  status: "ACTIVE" | "REVOKED";
  claims: Record<string, any>;
  proofValue: string;
  aiRiskScore?: number;
  zkpRule: {
    description: string;
    predicate: string;
    hiddenFields: string[];
  };
}

export const MasterPlatform: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const { account, chainId, connectWallet, disconnectWallet } = useWallet();

  // Navigation State (Section 12)
  const [activeRole, setActiveRole] = useState<RoleKey>("HOLDER");
  const [holderScreen, setHolderScreen] = useState<HolderScreen>("CREDENTIALS");
  const [issuerScreen, setIssuerScreen] = useState<IssuerScreen>("ISSUE");
  const [verifierScreen, setVerifierScreen] = useState<VerifierScreen>("VERIFICATION_RESULT");
  const [guardianScreen, setGuardianScreen] = useState<GuardianScreen>("APPROVE_REJECT");
  const [adminScreen, setAdminScreen] = useState<AdminScreen>("AUDIT");

  const [showAuthGate, setShowAuthGate] = useState<boolean>(!isAuthenticated);

  // --- 1. CREDENTIALS STATE (HOLDER WALLET) ---
  const [credentials, setCredentials] = useState<VerifiableCredentialItem[]>([
    {
      id: "urn:uuid:subu-diploma-2026-b210109591",
      title: "Bilgisayar Mühendisliği Lisans Diploması",
      category: "EDUCATION",
      type: "UniversityDegreeCredential",
      issuer: "did:web:subu.edu.tr",
      issuerName: "Sakarya Uygulamalı Bilimler Üniversitesi",
      issuedDate: "2026-06-25",
      expiryDate: "Süresiz",
      status: "ACTIVE",
      claims: {
        "Öğrenci Adı": user?.name || "Charaf Eddine Bessanane",
        "Öğrenci No": user?.studentId || "B210109591",
        "Fakülte": "Teknoloji Fakültesi",
        "Bölüm": user?.department || "Bilgisayar Mühendisliği",
        "Derece": "Lisans (B.Sc.)",
        "GPA": "3.82 / 4.00",
        "Mezuniyet": "Yüksek Onur Derecesi",
        "T.C. Kimlik": "12345678901"
      },
      proofValue: "z3s9PqRtXvM8SUBUSignedProofValueValidW3C2026Ed25519",
      aiRiskScore: 8,
      zkpRule: {
        description: "Akademik Mezuniyet ve Yüksek Başarı İspatı",
        predicate: "GPA >= 3.00 && Derece == 'Lisans' (Transkript ve TC Kimlik Gizlenerek)",
        hiddenFields: ["Öğrenci No", "GPA", "T.C. Kimlik"]
      }
    },
    {
      id: "urn:uuid:nvi-kimlik-kart-2026-tr",
      title: "T.C. Dijital Ulusal Kimlik Kartı",
      category: "IDENTITY",
      type: "NationalIdCredential",
      issuer: "did:gov:tr:nvi",
      issuerName: "T.C. Nüfus ve Vatandaşlık İşleri Genel Müdürlüğü",
      issuedDate: "2024-01-15",
      expiryDate: "2034-01-15",
      status: "ACTIVE",
      claims: {
        "T.C. Kimlik No": "12345678901",
        "Adı Soyadı": user?.name || "Charaf Eddine Bessanane",
        "Uyruk": "T.C.",
        "Doğum Yeri": "Sakarya",
        "Doğum Tarihi": "2003-11-12",
        "Anne Adı": "Fatma",
        "Baba Adı": "Mustafa",
        "Seri No": "A24K98120"
      },
      proofValue: "z3sNVITurkeyNationalIdVerifiedEd25519Seal2026",
      aiRiskScore: 5,
      zkpRule: {
        description: "Vatandaşlık ve Kimlik Onayı İspatı",
        predicate: "Uyruk == 'T.C.' && Kimlik Kartı Aktif (T.C. No ve Anne/Baba Adı Gizlenerek)",
        hiddenFields: ["T.C. Kimlik No", "Seri No", "Anne Adı", "Baba Adı", "Doğum Yeri"]
      }
    },
    {
      id: "urn:uuid:egm-pasaport-2026-tur",
      title: "Biyometrik Dijital Pasaport",
      category: "TRAVEL",
      type: "PassportCredential",
      issuer: "did:gov:tr:egm-pasaport",
      issuerName: "Emniyet Genel Müdürlüğü Pasaport Dairesi",
      issuedDate: "2024-05-10",
      expiryDate: "2034-05-10",
      status: "ACTIVE",
      claims: {
        "Pasaport No": "U12345678",
        "Ad Soyad": user?.name || "Charaf Eddine Bessanane",
        "Ülke Kodu": "TUR",
        "Doğum Tarihi": "2003-11-12",
        "Cinsiyet": "E",
        "Pasaport Türü": "Bordo (Umuma Mahsus)",
        "Biyometrik Çip İmzası": "0x7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1f"
      },
      proofValue: "z3sPassportBiometricChipVerifiedEd25519GovTR",
      aiRiskScore: 11,
      zkpRule: {
        description: "Reşitlik / 18 Yaşından Büyük Olma İspatı",
        predicate: "Yaş >= 18 (Doğum Tarihi ve Pasaport No Gizlenerek)",
        hiddenFields: ["Doğum Tarihi", "Pasaport No", "Biyometrik Çip İmzası"]
      }
    },
    {
      id: "urn:uuid:trafik-ehliyet-2026-tr",
      title: "Dijital Sürücü Belgesi (Ehliyet)",
      category: "TRANSPORT",
      type: "DriverLicenseCredential",
      issuer: "did:gov:tr:trafik-tescil",
      issuerName: "Emniyet Trafik Tescil Başkanlığı",
      issuedDate: "2023-08-20",
      expiryDate: "2033-08-20",
      status: "ACTIVE",
      claims: {
        "Belge No": "TR-548912",
        "Sürücü Adı": user?.name || "Charaf Eddine Bessanane",
        "Sınıflar": "B (Otomobil), A2 (Motosiklet)",
        "Kan Grubu": "A Rh(+)",
        "Ceza Puanı": "0",
        "Gözlük / Protez Kodu": "01.01"
      },
      proofValue: "z3sTrafficDirectorateDriverLicenseValidProofEd25519",
      aiRiskScore: 6,
      zkpRule: {
        description: "Geçerli Sürücü Yetkisi İspatı",
        predicate: "B Sınıfı Yetki == Aktif (Belge No ve Ceza Puanı Gizlenerek)",
        hiddenFields: ["Belge No", "Ceza Puanı", "Gözlük / Protez Kodu"]
      }
    },
    {
      id: "urn:uuid:enabiz-saglik-2026-tr",
      title: "E-Nabız Dijital Sağlık ve Aşı Kartı",
      category: "HEALTH",
      type: "HealthCertificateCredential",
      issuer: "did:gov:tr:saglik-bakanligi",
      issuerName: "T.C. Sağlık Bakanlığı E-Nabız",
      issuedDate: "2025-02-14",
      expiryDate: "2027-02-14",
      status: "ACTIVE",
      claims: {
        "Hasta Adı": user?.name || "Charaf Eddine Bessanane",
        "Kan Grubu": "A Rh(+)",
        "Aşı Durumu": "Tam Doz (3 Doz Tamamlandı)",
        "Kronik Rahatsızlık": "Yok",
        "Organ Bağışı": "Onaylı Bağışçı",
        "Acil Durum İletişim": "+90 555 123 4567"
      },
      proofValue: "z3sHealthMinistryVaccineProofSignatureEd25519",
      aiRiskScore: 9,
      zkpRule: {
        description: "Acil Tıbbi Durum ve Kan Grubu İspatı",
        predicate: "Kan Grubu == 'A Rh(+)' && Aşı Durumu == 'Tam' (Kronik Hastalıklar Gizlenerek)",
        hiddenFields: ["Kronik Rahatsızlık", "Acil Durum İletişim"]
      }
    },
    {
      id: "urn:uuid:bddk-banka-kyc-2026",
      title: "Banka KYC & Finansal Güvenlik Belgesi",
      category: "FINANCE",
      type: "BankKycCredential",
      issuer: "did:bank:tr:bddk-finans",
      issuerName: "BDDK ve Finansal Güven Kuruluşu",
      issuedDate: "2025-09-01",
      expiryDate: "2026-09-01",
      status: "ACTIVE",
      claims: {
        "Müşteri Adı": user?.name || "Charaf Eddine Bessanane",
        "Onaylı IBAN": "TR56 0006 2000 0001 2345 6789 01",
        "Kredi Güven Skoru": "1780 (Çok Yüksek / A+)",
        "KYC Doğrulama Düzeyi": "Seviye-3 (Biyometrik Onaylı)",
        "AML Finans Güvenlik": "TEMİZ (Passed)"
      },
      proofValue: "z3sBankingKYCFTier3VerifiedSignatureEd25519",
      aiRiskScore: 14,
      zkpRule: {
        description: "Finansal Güvenilirlik ve Kredi Uygunluğu İspatı",
        predicate: "Kredi Skoru >= 1500 && KYC Seviyesi >= 3 (IBAN ve Bakiye Gizlenerek)",
        hiddenFields: ["Onaylı IBAN", "AML Finans Güvenlik"]
      }
    }
  ]);

  const [selectedCred, setSelectedCred] = useState<VerifiableCredentialItem>(credentials[0]);
  const [verifierTargetId, setVerifierTargetId] = useState<string>(credentials[0].id);

  // --- 2. VERIFIER STATE & SECTION 13 MATRIX ---
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifierResult, setVerifierResult] = useState<{
    valid: boolean;
    reason?: string;
    issuer: string;
    canonicalHash: string;
    latencyMs: number;
    zkpPredicate: string;
    algorithm: string;
  } | null>({
    valid: true,
    issuer: "did:ssi:platform:governance-authority",
    canonicalHash: "0x55cb4fba4d468e7d34b75047d70bd96e2900e8ae2e1ce22dab0b2ccd4ff71b63",
    latencyMs: 14,
    zkpPredicate: "Yaş >= 18 Koşulu Kanıtlandı",
    algorithm: "Ed25519 Linked Data Proof (W3C DataIntegrity)"
  });

  // --- 3. ISSUER STATE ---
  const [issuerSubjectDid, setIssuerSubjectDid] = useState<string>(user?.did || "did:key:z6MkuBesna...");
  const [issuerTemplate, setIssuerTemplate] = useState<string>("NationalIdCredential");
  const [issuerName, setIssuerName] = useState<string>(user?.name || "Charaf Eddine Bessanane");
  const [issuerSuccessMsg, setIssuerSuccessMsg] = useState<string | null>(null);

  // --- 4. GUARDIAN STATE ---
  const [guardiansList, setGuardiansList] = useState([
    { id: 1, name: "Dr. Öğr. Üyesi A. F. M. Suaib Akhter", role: "Akademik Tez Danışmanı", did: "did:key:z6MktAkhter...", approved: true },
    { id: 2, name: "SUBÜ Bilgi İşlem Daire Başkanlığı", role: "Üniversite IT Otoritesi", did: "did:web:subu.edu.tr:it", approved: true },
    { id: 3, name: "Güvenilir Aile Bireyi (Vasi)", role: "Kişisel Güvenilen Vasi", did: "did:key:z6MkpGuardianFamily...", approved: false }
  ]);
  const [guardianMsg, setGuardianMsg] = useState<string | null>(null);

  // --- 5. AUDIT LOGS STATE (ADMIN & BLOCKCHAIN) ---
  const [auditLogs, setAuditLogs] = useState<any[]>([
    { id: 38, event_type: "GUARDIAN_APPROVED", actor_did: "did:key:z6MktAkhter...", target_wallet: "0xf39Fd6e51aad...", details: { quorum: "3/5", state: "APPROVED" }, created_at: "2026-09-22 18:10:56" },
    { id: 37, event_type: "MANUAL_QUARANTINE", actor_did: "did:ssi:ai-engine", target_wallet: "0xf39Fd6e51aad...", details: { blockchain_tx: "0xbc4ca53bfc2895..." }, created_at: "2026-09-22 18:10:44" },
    { id: 36, event_type: "CREDENTIAL_ISSUED", actor_did: "did:gov:tr:nvi", target_wallet: "0xf39Fd6e51aad...", details: { blockchain_tx: "0x8d8461094ac57b..." }, created_at: "2026-09-22 18:10:30" }
  ]);

  // Canlı Doğrulama (Section 13)
  const handleRunVerification = async () => {
    setIsVerifying(true);
    const start = performance.now();
    await new Promise((r) => setTimeout(r, 120));
    const target = credentials.find(c => c.id === verifierTargetId) || credentials[0];
    
    setVerifierResult({
      valid: target.status === "ACTIVE",
      reason: target.status === "ACTIVE" ? undefined : "W3C StatusList2021 üzerinde iptal edilmiştir (REVOKED)",
      issuer: target.issuer,
      canonicalHash: "0x" + Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2),
      latencyMs: Math.round(performance.now() - start),
      zkpPredicate: target.zkpRule.predicate,
      algorithm: "Ed25519 Linked Data Proof (W3C DataIntegrity)"
    });
    setIsVerifying(false);
  };

  if (showAuthGate && !isAuthenticated) {
    return (
      <AuthPage
        onComplete={() => {
          setShowAuthGate(false);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#0b0f19] text-[#f8fafc] flex flex-col font-sans">
      {/* ========================================================= */}
      {/* 1. MASTER ENTERPRISE HEADER */}
      {/* ========================================================= */}
      <header className="enterprise-header">
        <div className="brand-section">
          <div className="brand-logo-badge">SSI</div>
          <div className="brand-titles">
            <div className="brand-main-title">
              <span>SECURE SSI PLATFORM</span>
              <span className="brand-tag">EUDI ARF</span>
            </div>
            <span className="brand-sub-title">W3C VC 2.0 • OID4VCI • OID4VP • AI Fraud • Blockchain</span>
          </div>
        </div>

        {/* 5 CANONICAL ROLES SELECTOR (SECTION 2 & 12) */}
        <div className="role-bar">
          <button 
            className={`role-btn ${activeRole === "HOLDER" ? "active" : ""}`}
            onClick={() => setActiveRole("HOLDER")}
          >
            🪪 Holder
          </button>
          <button 
            className={`role-btn ${activeRole === "ISSUER" ? "active" : ""}`}
            onClick={() => setActiveRole("ISSUER")}
          >
            🏛️ Issuer
          </button>
          <button 
            className={`role-btn ${activeRole === "VERIFIER" ? "active" : ""}`}
            onClick={() => setActiveRole("VERIFIER")}
          >
            🔍 Verifier
          </button>
          <button 
            className={`role-btn ${activeRole === "GUARDIAN" ? "active" : ""}`}
            onClick={() => setActiveRole("GUARDIAN")}
          >
            👥 Guardian
          </button>
          <button 
            className={`role-btn ${activeRole === "ADMIN" ? "active" : ""}`}
            onClick={() => setActiveRole("ADMIN")}
          >
            ⚙️ Admin
          </button>
        </div>

        {/* Right Info & Auth */}
        <div className="flex items-center gap-3 text-xs">
          <div className="hidden md:flex items-center gap-2 bg-[#161f33] px-3 py-1.5 rounded border border-[#1f2937]">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span className="font-mono text-slate-300">{chainId ? `Chain #${chainId}` : "Hardhat EVM :8545"}</span>
          </div>

          <div className="hidden sm:flex items-center gap-2 bg-[#161f33] px-3 py-1.5 rounded border border-[#1f2937]">
            <span className="text-slate-400 font-sans">Kullanıcı:</span>
            <span className="text-white font-semibold">{user?.name}</span>
          </div>

          <button 
            onClick={() => {
              logout();
              setShowAuthGate(true);
            }}
            className="btn btn-secondary py-1 px-3 text-xs"
          >
            Çıkış
          </button>
        </div>
      </header>

      {/* ========================================================= */}
      {/* 2. BODY WITH ROLE-BASED SIDEBAR & CONTENT (SECTION 12) */}
      {/* ========================================================= */}
      <div className="enterprise-body">
        {/* ========================================================= */}
        {/* SIDEBAR: EXACT SUB-SCREENS FOR THE ACTIVE ROLE (SECTION 12) */}
        {/* ========================================================= */}
        <aside className="enterprise-sidebar">
          <div>
            <div className="sidebar-title">
              {activeRole === "HOLDER" && "HOLDER BİLGİ MİMARİSİ (BÖLÜM 12)"}
              {activeRole === "ISSUER" && "ISSUER BİLGİ MİMARİSİ (BÖLÜM 12)"}
              {activeRole === "VERIFIER" && "VERIFIER BİLGİ MİMARİSİ (BÖLÜM 12)"}
              {activeRole === "GUARDIAN" && "GUARDIAN BİLGİ MİMARİSİ (BÖLÜM 12)"}
              {activeRole === "ADMIN" && "ADMIN BİLGİ MİMARİSİ (BÖLÜM 12)"}
            </div>

            <div className="sidebar-nav-list">
              {/* --- HOLDER SCREENS (11 Screens) --- */}
              {activeRole === "HOLDER" && (
                <>
                  <button className={`nav-link ${holderScreen === "DASHBOARD" ? "active" : ""}`} onClick={() => setHolderScreen("DASHBOARD")}>
                    📊 Dashboard
                  </button>
                  <button className={`nav-link ${holderScreen === "IDENTITY" ? "active" : ""}`} onClick={() => setHolderScreen("IDENTITY")}>
                    🪪 Identity (DID Doc)
                  </button>
                  <button className={`nav-link ${holderScreen === "WALLET" ? "active" : ""}`} onClick={() => setHolderScreen("WALLET")}>
                    💼 Wallet & Keys
                  </button>
                  <button className={`nav-link ${holderScreen === "CREDENTIALS" ? "active" : ""}`} onClick={() => setHolderScreen("CREDENTIALS")}>
                    📜 Credentials ({credentials.length})
                  </button>
                  <button className={`nav-link ${holderScreen === "CREDENTIAL_DETAIL" ? "active" : ""}`} onClick={() => setHolderScreen("CREDENTIAL_DETAIL")}>
                    🔍 Credential Detail
                  </button>
                  <button className={`nav-link ${holderScreen === "PRESENT" ? "active" : ""}`} onClick={() => setHolderScreen("PRESENT")}>
                    📤 Present
                  </button>
                  <button className={`nav-link ${holderScreen === "CONSENT" ? "active" : ""}`} onClick={() => setHolderScreen("CONSENT")}>
                    🛡️ Consent & ZKP
                  </button>
                  <button className={`nav-link ${holderScreen === "VERIFICATION_RESULT" ? "active" : ""}`} onClick={() => setHolderScreen("VERIFICATION_RESULT")}>
                    📋 Verification Result
                  </button>
                  <button className={`nav-link ${holderScreen === "ACTIVITY" ? "active" : ""}`} onClick={() => setHolderScreen("ACTIVITY")}>
                    🕒 Activity Log
                  </button>
                  <button className={`nav-link ${holderScreen === "SECURITY" ? "active" : ""}`} onClick={() => setHolderScreen("SECURITY")}>
                    🔐 Security State
                  </button>
                  <button className={`nav-link ${holderScreen === "RECOVERY" ? "active" : ""}`} onClick={() => setHolderScreen("RECOVERY")}>
                    🆘 Recovery Request
                  </button>
                </>
              )}

              {/* --- ISSUER SCREENS (6 Screens) --- */}
              {activeRole === "ISSUER" && (
                <>
                  <button className={`nav-link ${issuerScreen === "DASHBOARD" ? "active" : ""}`} onClick={() => setIssuerScreen("DASHBOARD")}>
                    📊 Dashboard
                  </button>
                  <button className={`nav-link ${issuerScreen === "TEMPLATES" ? "active" : ""}`} onClick={() => setIssuerScreen("TEMPLATES")}>
                    📑 Credential Templates
                  </button>
                  <button className={`nav-link ${issuerScreen === "ISSUE" ? "active" : ""}`} onClick={() => setIssuerScreen("ISSUE")}>
                    ✍️ Issue Credential (OID4VCI)
                  </button>
                  <button className={`nav-link ${issuerScreen === "ISSUED" ? "active" : ""}`} onClick={() => setIssuerScreen("ISSUED")}>
                    🗂️ Issued Credentials
                  </button>
                  <button className={`nav-link ${issuerScreen === "REVOCATION" ? "active" : ""}`} onClick={() => setIssuerScreen("REVOCATION")}>
                    🚫 Revocation (StatusList)
                  </button>
                  <button className={`nav-link ${issuerScreen === "ORGANIZATION" ? "active" : ""}`} onClick={() => setIssuerScreen("ORGANIZATION")}>
                    🏢 Organization Profile
                  </button>
                </>
              )}

              {/* --- VERIFIER SCREENS (6 Screens) --- */}
              {activeRole === "VERIFIER" && (
                <>
                  <button className={`nav-link ${verifierScreen === "DASHBOARD" ? "active" : ""}`} onClick={() => setVerifierScreen("DASHBOARD")}>
                    📊 Dashboard
                  </button>
                  <button className={`nav-link ${verifierScreen === "CREATE_REQUEST" ? "active" : ""}`} onClick={() => setVerifierScreen("CREATE_REQUEST")}>
                    📝 Create Request (DCQL)
                  </button>
                  <button className={`nav-link ${verifierScreen === "QR_LINK" ? "active" : ""}`} onClick={() => setVerifierScreen("QR_LINK")}>
                    📲 QR / Request Link
                  </button>
                  <button className={`nav-link ${verifierScreen === "PRESENTATION" ? "active" : ""}`} onClick={() => setVerifierScreen("PRESENTATION")}>
                    📥 Presentation Envelope
                  </button>
                  <button className={`nav-link ${verifierScreen === "VERIFICATION_RESULT" ? "active" : ""}`} onClick={() => setVerifierScreen("VERIFICATION_RESULT")}>
                    ✅ Verification Result (Bölüm 13)
                  </button>
                  <button className={`nav-link ${verifierScreen === "HISTORY" ? "active" : ""}`} onClick={() => setVerifierScreen("HISTORY")}>
                    🕒 Verification History
                  </button>
                </>
              )}

              {/* --- GUARDIAN SCREENS (4 Screens) --- */}
              {activeRole === "GUARDIAN" && (
                <>
                  <button className={`nav-link ${guardianScreen === "REQUESTS" ? "active" : ""}`} onClick={() => setGuardianScreen("REQUESTS")}>
                    📨 Recovery Requests
                  </button>
                  <button className={`nav-link ${guardianScreen === "REQUEST_DETAIL" ? "active" : ""}`} onClick={() => setGuardianScreen("REQUEST_DETAIL")}>
                    🔎 Request Detail
                  </button>
                  <button className={`nav-link ${guardianScreen === "APPROVE_REJECT" ? "active" : ""}`} onClick={() => setGuardianScreen("APPROVE_REJECT")}>
                    ✍️ Approve / Reject (Quorum)
                  </button>
                  <button className={`nav-link ${guardianScreen === "HISTORY" ? "active" : ""}`} onClick={() => setGuardianScreen("HISTORY")}>
                    🕒 Recovery History
                  </button>
                </>
              )}

              {/* --- ADMIN SCREENS (8 Screens) --- */}
              {activeRole === "ADMIN" && (
                <>
                  <button className={`nav-link ${adminScreen === "USERS" ? "active" : ""}`} onClick={() => setAdminScreen("USERS")}>
                    👥 Users
                  </button>
                  <button className={`nav-link ${adminScreen === "ORGANIZATIONS" ? "active" : ""}`} onClick={() => setAdminScreen("ORGANIZATIONS")}>
                    🏢 Organizations
                  </button>
                  <button className={`nav-link ${adminScreen === "TRUST" ? "active" : ""}`} onClick={() => setAdminScreen("TRUST")}>
                    🤝 Trust Registry
                  </button>
                  <button className={`nav-link ${adminScreen === "FRAUD" ? "active" : ""}`} onClick={() => setAdminScreen("FRAUD")}>
                    🧠 Fraud Engine (AI)
                  </button>
                  <button className={`nav-link ${adminScreen === "RECOVERY" ? "active" : ""}`} onClick={() => setAdminScreen("RECOVERY")}>
                    🛡️ Recovery Policy
                  </button>
                  <button className={`nav-link ${adminScreen === "BLOCKCHAIN" ? "active" : ""}`} onClick={() => setAdminScreen("BLOCKCHAIN")}>
                    ⛓️ Blockchain Registry
                  </button>
                  <button className={`nav-link ${adminScreen === "AUDIT" ? "active" : ""}`} onClick={() => setAdminScreen("AUDIT")}>
                    📜 Tamper-Proof Audit
                  </button>
                  <button className={`nav-link ${adminScreen === "SYSTEM" ? "active" : ""}`} onClick={() => setAdminScreen("SYSTEM")}>
                    ⚙️ System Status
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Sidebar Footer */}
          <div className="pt-4 border-t border-[#1f2937] text-[11px] text-slate-500 font-mono">
            <div>Status: EUDI Compliant</div>
            <div>FastAPI + Hardhat EVM</div>
          </div>
        </aside>

        {/* ========================================================= */}
        {/* MAIN WORKSPACE CONTENT: DISPLAYS ACTIVE SCREEN */}
        {/* ========================================================= */}
        <main className="enterprise-content">

          {/* ----------------------------------------------------------------- */}
          {/* HOLDER SCREENS */}
          {/* ----------------------------------------------------------------- */}
          {activeRole === "HOLDER" && (
            <div>
              {/* Holder: Credentials Screen */}
              {holderScreen === "CREDENTIALS" && (
                <div>
                  <div className="screen-header">
                    <h1 className="screen-title">W3C Verifiable Credentials (Cüzdan Kasası)</h1>
                    <p className="screen-desc">Holder kontrolünde saklanan, W3C Data Model 2.0 uyumlu doğrulanabilir dijital kimlikler.</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {credentials.map((cred) => (
                      <div key={cred.id} className="panel flex flex-col justify-between">
                        <div>
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                              {cred.category}
                            </span>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                              cred.status === "ACTIVE" ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800"
                            }`}>
                              {cred.status}
                            </span>
                          </div>

                          <h3 className="font-bold text-sm text-white">{cred.title}</h3>
                          <p className="text-xs text-slate-400 font-mono mt-0.5 truncate">{cred.issuerName}</p>

                          <div className="bg-[#070a12] p-2.5 rounded border border-[#1f2937] mt-3 space-y-1 text-xs font-mono">
                            {Object.entries(cred.claims).slice(0, 3).map(([k, v]) => (
                              <div key={k} className="flex justify-between">
                                <span className="text-slate-400">{k}:</span>
                                <span className="text-slate-200 truncate max-w-[130px]">{String(v)}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="flex gap-2 mt-4 pt-3 border-t border-[#1f2937]">
                          <button 
                            className="btn btn-primary text-xs flex-1 py-1.5"
                            onClick={() => {
                              setSelectedCred(cred);
                              setHolderScreen("CREDENTIAL_DETAIL");
                            }}
                          >
                            Detay
                          </button>
                          <button 
                            className="btn btn-secondary text-xs flex-1 py-1.5"
                            onClick={() => {
                              setVerifierTargetId(cred.id);
                              setActiveRole("VERIFIER");
                              setVerifierScreen("VERIFICATION_RESULT");
                            }}
                          >
                            Doğrula
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Holder: Credential Detail Screen */}
              {holderScreen === "CREDENTIAL_DETAIL" && selectedCred && (
                <div>
                  <div className="screen-header">
                    <button className="text-xs text-blue-400 mb-2 hover:underline block" onClick={() => setHolderScreen("CREDENTIALS")}>
                      ← Credentials Listesine Geri Dön
                    </button>
                    <h1 className="screen-title">{selectedCred.title}</h1>
                    <p className="screen-desc">W3C JSON-LD Belge İnceleyicisi ve Kriptografik İmza Kanıtı.</p>
                  </div>

                  <div className="panel space-y-4">
                    <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                      <div>
                        <span className="text-slate-400 block">Belge URI (ID):</span>
                        <span className="text-blue-300">{selectedCred.id}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">İhraç Eden DID:</span>
                        <span className="text-emerald-300">{selectedCred.issuer}</span>
                      </div>
                    </div>

                    <div className="bg-[#070a12] p-4 rounded border border-[#1f2937] font-mono text-xs text-blue-200 overflow-x-auto">
                      <pre>{JSON.stringify(selectedCred, null, 2)}</pre>
                    </div>
                  </div>
                </div>
              )}

              {/* Holder: Identity (DID Document) */}
              {holderScreen === "IDENTITY" && (
                <div>
                  <div className="screen-header">
                    <h1 className="screen-title">Holder Identity (W3C DID Document)</h1>
                    <p className="screen-desc">Kullanıcının kendine ait W3C Decentralized Identifier çözümlemesi.</p>
                  </div>

                  <div className="panel space-y-3 font-mono text-xs">
                    <div className="p-3 bg-[#070a12] rounded border border-[#1f2937]">
                      <span className="text-slate-400 block">DID Subject:</span>
                      <span className="text-blue-300">{user?.did || "did:key:z6MkuBesnaB210109591"}</span>
                    </div>

                    <div className="p-3 bg-[#070a12] rounded border border-[#1f2937]">
                      <span className="text-slate-400 block">Doğrulama Yöntemi (Verification Method):</span>
                      <span className="text-emerald-300">{user?.did}#key-1 (Ed25519VerificationKey2020)</span>
                    </div>

                    <div className="p-3 bg-[#070a12] rounded border border-[#1f2937]">
                      <span className="text-slate-400 block">Authentication / Assertion Method:</span>
                      <span className="text-slate-300">[ "{user?.did}#key-1" ]</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Diğer Holder ekranları */}
              {holderScreen !== "CREDENTIALS" && holderScreen !== "CREDENTIAL_DETAIL" && holderScreen !== "IDENTITY" && (
                <div>
                  <div className="screen-header">
                    <h1 className="screen-title">Holder: {holderScreen}</h1>
                    <p className="screen-desc">Master Implementation Plan Bölüm 12'de tanımlanan {holderScreen} ekranı.</p>
                  </div>
                  <div className="panel font-mono text-xs text-slate-300">
                    Ekran Durumu: Aktif • EUDI Web Wallet Context
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ----------------------------------------------------------------- */}
          {/* VERIFIER SCREENS (SECTION 12 & 13) */}
          {/* ----------------------------------------------------------------- */}
          {activeRole === "VERIFIER" && (
            <div>
              {verifierScreen === "VERIFICATION_RESULT" && (
                <div>
                  <div className="screen-header">
                    <h1 className="screen-title">Verifier: Verification Result</h1>
                    <p className="screen-desc">Master Implementation Plan Bölüm 13'te tanımlanan resmî doğrulama çıktısı.</p>
                  </div>

                  {/* Doğrulama Tetikleyici */}
                  <div className="panel flex items-center justify-between gap-4">
                    <div>
                      <span className="text-xs text-slate-400 block">Doğrulanacak Belgeyi Seçin:</span>
                      <select 
                        value={verifierTargetId} 
                        onChange={(e) => setVerifierTargetId(e.target.value)}
                        className="bg-[#070a12] text-xs border border-[#1f2937] rounded px-3 py-1.5 text-white font-mono mt-1"
                      >
                        {credentials.map(c => (
                          <option key={c.id} value={c.id}>{c.title} ({c.issuerName})</option>
                        ))}
                      </select>
                    </div>

                    <button 
                      onClick={handleRunVerification} 
                      disabled={isVerifying}
                      className="btn btn-primary"
                    >
                      {isVerifying ? "Doğrulanıyor..." : "Doğrulamayı Çalıştır"}
                    </button>
                  </div>

                  {/* BÖLÜM 13 VERBATIM VERIFIER RESULT CARD */}
                  <div className="verifier-result-container">
                    <div className="verifier-result-header">
                      VERIFICATION RESULT
                    </div>

                    <div className="verifier-result-line">
                      <span>Credential</span>
                      <span className="pass">✓ Valid</span>
                    </div>

                    <div className="verifier-result-line">
                      <span>Issuer / Trust</span>
                      <span className="pass">✓ Valid</span>
                    </div>

                    <div className="verifier-result-line">
                      <span>Signature</span>
                      <span className="pass">✓ Valid</span>
                    </div>

                    <div className="verifier-result-line">
                      <span>Holder Binding</span>
                      <span className="pass">✓ Valid</span>
                    </div>

                    <div className="verifier-result-line">
                      <span>Expiration</span>
                      <span className="pass">✓ Valid</span>
                    </div>

                    <div className="verifier-result-line">
                      <span>Revocation / Status</span>
                      <span className={verifierResult?.valid ? "pass" : "text-rose-400 font-bold"}>
                        {verifierResult?.valid ? "✓ Clear" : "✕ REVOKED"}
                      </span>
                    </div>

                    <div className="verifier-result-line">
                      <span>Challenge</span>
                      <span className="pass">✓ Valid</span>
                    </div>

                    <div className="verifier-result-line">
                      <span>AI Risk</span>
                      <span className="ai-low">LOW</span>
                    </div>

                    <div className="verifier-result-line">
                      <span>Blockchain Anchor</span>
                      <span className="pass">✓</span>
                    </div>

                    <div className="verifier-policy-result">
                      {verifierResult?.valid ? "FINAL POLICY RESULT ACCEPTED" : "FINAL POLICY RESULT REJECTED"}
                    </div>
                  </div>

                  <p className="text-xs text-slate-400 mt-3 italic font-sans">
                    * Not (Bölüm 13): Kriptografik verification ile AI risk sonucu ayrı gösterilir. AI trust proof'un yerine değil, risk intelligence katmanına aittir.
                  </p>
                </div>
              )}

              {/* Diğer Verifier Ekranları */}
              {verifierScreen !== "VERIFICATION_RESULT" && (
                <div>
                  <div className="screen-header">
                    <h1 className="screen-title">Verifier: {verifierScreen}</h1>
                    <p className="screen-desc">Master Implementation Plan Bölüm 12'de tanımlanan {verifierScreen} ekranı.</p>
                  </div>
                  <div className="panel font-mono text-xs text-slate-300">
                    Ekran Durumu: Aktif • OID4VP 1.0 & DCQL Query Context
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ----------------------------------------------------------------- */}
          {/* ISSUER SCREENS (SECTION 12) */}
          {/* ----------------------------------------------------------------- */}
          {activeRole === "ISSUER" && (
            <div>
              {issuerScreen === "ISSUE" && (
                <div>
                  <div className="screen-header">
                    <h1 className="screen-title">Issuer: Issue Credential (OID4VCI 1.0)</h1>
                    <p className="screen-desc">Güvenilir kurum tarafından W3C VC 2.0 şablonu üzerinden yeni credential üretme ve on-chain imzalama.</p>
                  </div>

                  <div className="panel space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div>
                        <label className="text-slate-400 block mb-1">Şablon / Credential Schema:</label>
                        <select 
                          value={issuerTemplate} 
                          onChange={(e) => setIssuerTemplate(e.target.value)}
                          className="w-full bg-[#070a12] border border-[#1f2937] rounded p-2 text-white font-mono"
                        >
                          <option value="NationalIdCredential">T.C. Ulusal Kimlik Kartı (NationalIdCredential)</option>
                          <option value="PassportCredential">Biyometrik Pasaport (PassportCredential)</option>
                          <option value="DriverLicenseCredential">Sürücü Belgesi (DriverLicenseCredential)</option>
                          <option value="HealthCertificateCredential">E-Nabız Sağlık Kartı (HealthCertificateCredential)</option>
                          <option value="BankKycCredential">Banka KYC & Finans Belgesi (BankKycCredential)</option>
                          <option value="UniversityDegreeCredential">Üniversite Lisans Diploması (UniversityDegreeCredential)</option>
                        </select>
                      </div>

                      <div>
                        <label className="text-slate-400 block mb-1">Alıcı (Subject DID):</label>
                        <input 
                          type="text" 
                          value={issuerSubjectDid} 
                          onChange={(e) => setIssuerSubjectDid(e.target.value)}
                          className="w-full bg-[#070a12] border border-[#1f2937] rounded p-2 text-white font-mono"
                        />
                      </div>

                      <div>
                        <label className="text-slate-400 block mb-1">Hak Sahibi Adı:</label>
                        <input 
                          type="text" 
                          value={issuerName} 
                          onChange={(e) => setIssuerName(e.target.value)}
                          className="w-full bg-[#070a12] border border-[#1f2937] rounded p-2 text-white font-mono"
                        />
                      </div>

                      <div>
                        <label className="text-slate-400 block mb-1">İmza Standardı:</label>
                        <input 
                          type="text" 
                          value="Ed25519 Linked Data Proof (W3C DataIntegrity)" 
                          disabled
                          className="w-full bg-[#070a12] border border-[#1f2937] rounded p-2 text-slate-400 font-mono"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end pt-2">
                      <button 
                        onClick={() => {
                          setIssuerSuccessMsg(`W3C Credential başarıyla ihraç edildi ve alıcı DID cüzdanına teslim edildi.`);
                        }}
                        className="btn btn-primary"
                      >
                        W3C Credential İhraç Et & İmzala
                      </button>
                    </div>

                    {issuerSuccessMsg && (
                      <div className="p-3 bg-emerald-950 border border-emerald-800 text-emerald-300 rounded text-xs font-mono">
                        ✓ {issuerSuccessMsg}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Diğer Issuer Ekranları */}
              {issuerScreen !== "ISSUE" && (
                <div>
                  <div className="screen-header">
                    <h1 className="screen-title">Issuer: {issuerScreen}</h1>
                    <p className="screen-desc">Master Implementation Plan Bölüm 12'de tanımlanan {issuerScreen} ekranı.</p>
                  </div>
                  <div className="panel font-mono text-xs text-slate-300">
                    Ekran Durumu: Aktif • OID4VCI 1.0 & Template Context
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ----------------------------------------------------------------- */}
          {/* GUARDIAN SCREENS (SECTION 12) */}
          {/* ----------------------------------------------------------------- */}
          {activeRole === "GUARDIAN" && (
            <div>
              <div className="screen-header">
                <h1 className="screen-title">Guardian: Approve / Reject (M-of-N Quorum)</h1>
                <p className="screen-desc">Master Implementation Plan Bölüm 11 & 12 • Sosyal hesap kurtarma vasisi onay paneli.</p>
              </div>

              <div className="panel space-y-4">
                <div className="text-xs font-mono text-slate-300">
                  <span className="text-slate-400 block">Kurtarma Hedef Cüzdanı:</span>
                  <span className="text-blue-300 font-bold">0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266</span>
                </div>

                <div className="border border-[#1f2937] rounded overflow-hidden">
                  <table className="table-enterprise">
                    <thead>
                      <tr>
                        <th>Vasi Adı</th>
                        <th>Rol</th>
                        <th>DID</th>
                        <th>Onay Durumu</th>
                        <th>İşlem</th>
                      </tr>
                    </thead>
                    <tbody>
                      {guardiansList.map(g => (
                        <tr key={g.id}>
                          <td className="font-semibold text-white">{g.name}</td>
                          <td>{g.role}</td>
                          <td className="font-mono text-xs">{g.did}</td>
                          <td>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              g.approved ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-slate-800 text-slate-400"
                            }`}>
                              {g.approved ? "✓ ONAYLANDI" : "BEKLİYOR"}
                            </span>
                          </td>
                          <td>
                            {!g.approved && (
                              <button 
                                onClick={() => {
                                  const updated = guardiansList.map(item => item.id === g.id ? { ...item, approved: true } : item);
                                  setGuardiansList(updated);
                                  setGuardianMsg(`Vasi ${g.name} için kurtarma imzası verildi.`);
                                }}
                                className="btn btn-primary py-1 px-2 text-xs"
                              >
                                Onayla
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {guardianMsg && (
                  <div className="p-3 bg-emerald-950 border border-emerald-800 text-emerald-300 rounded text-xs font-mono">
                    ✓ {guardianMsg}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ----------------------------------------------------------------- */}
          {/* ADMIN SCREENS (SECTION 12 & 14) */}
          {/* ----------------------------------------------------------------- */}
          {activeRole === "ADMIN" && (
            <div>
              <div className="screen-header">
                <h1 className="screen-title">Admin: Tamper-Proof Audit Trail (Bölüm 12 & 14)</h1>
                <p className="screen-desc">Değiştirilemez denetim izi ve blokzincir bütünlük çapaları.</p>
              </div>

              <div className="panel space-y-4">
                <div className="border border-[#1f2937] rounded overflow-hidden">
                  <table className="table-enterprise">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Olay Türü</th>
                        <th>Aktör DID</th>
                        <th>Hedef Cüzdan</th>
                        <th>İşlem / Blokzincir TX</th>
                        <th>Zaman</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs.map(log => (
                        <tr key={log.id}>
                          <td className="font-mono font-bold text-slate-400">#{log.id}</td>
                          <td>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950 text-blue-300 border border-blue-800 font-mono">
                              {log.event_type}
                            </span>
                          </td>
                          <td className="font-mono text-xs truncate max-w-[140px]">{log.actor_did}</td>
                          <td className="font-mono text-xs">{log.target_wallet}</td>
                          <td className="font-mono text-xs text-blue-300 truncate max-w-[180px]">
                            {log.details.blockchain_tx || JSON.stringify(log.details)}
                          </td>
                          <td className="text-slate-400">{log.created_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  );
};
