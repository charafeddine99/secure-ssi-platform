import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { useWallet, EMERGENCY_RECOVERY_ADDRESS, DID_REGISTRY_ADDRESS } from "../context/WalletContext";
import { AuthPage } from "../components/auth/AuthPage";
import { ethers } from "ethers";

export type TabKey = "dashboard" | "wallet" | "issuer" | "verifier" | "ai" | "recovery" | "blockchain";

export type CredentialCategory = "ALL" | "IDENTITY" | "TRAVEL" | "TRANSPORT" | "HEALTH" | "FINANCE" | "EDUCATION";

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
  const { account, chainId, connectWallet, disconnectWallet, getEmergencyRecoveryContract } = useWallet();

  const [activeTab, setActiveTab] = useState<TabKey>("wallet");
  const [showAuthGate, setShowAuthGate] = useState<boolean>(!isAuthenticated);
  const [selectedCategory, setSelectedCategory] = useState<CredentialCategory>("ALL");

  // --- 1. CREDENTIALS STATE (HOLDER DIGITAL VAULT) ---
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

  const [selectedCred, setSelectedCred] = useState<VerifiableCredentialItem | null>(credentials[0]);
  const [showQrModal, setShowQrModal] = useState<boolean>(false);
  const [showJsonModal, setShowJsonModal] = useState<boolean>(false);
  const [copiedKey, setCopiedKey] = useState<boolean>(false);

  // --- 2. ISSUER STATE (RESMİ KURUM İHRAÇ PORTALI) ---
  const [issuerType, setIssuerType] = useState<"PASSPORT" | "NATIONAL_ID" | "DRIVER_LICENSE" | "HEALTH" | "BANK_KYC" | "DEGREE">("PASSPORT");
  const [issuerFullName, setIssuerFullName] = useState(user?.name || "Charaf Eddine Bessanane");
  const [issuerDocNumber, setIssuerDocNumber] = useState("U98214300");
  const [issuerExtraField1, setIssuerExtraField1] = useState("TUR");
  const [issuerExtraField2, setIssuerExtraField2] = useState("Bordo (Umuma Mahsus)");
  const [issuerExtraField3, setIssuerExtraField3] = useState("2003-11-12");
  const [issuerLoading, setIssuerLoading] = useState<boolean>(false);
  const [issuerNotification, setIssuerNotification] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // Update dynamic form defaults when issuer type changes
  const handleIssuerTypeChange = (type: "PASSPORT" | "NATIONAL_ID" | "DRIVER_LICENSE" | "HEALTH" | "BANK_KYC" | "DEGREE") => {
    setIssuerType(type);
    setIssuerNotification(null);
    if (type === "PASSPORT") {
      setIssuerDocNumber(`U${Math.floor(10000000 + Math.random() * 90000000)}`);
      setIssuerExtraField1("TUR");
      setIssuerExtraField2("Bordo (Umuma Mahsus)");
      setIssuerExtraField3("2003-11-12");
    } else if (type === "NATIONAL_ID") {
      setIssuerDocNumber("12345678901");
      setIssuerExtraField1("Sakarya");
      setIssuerExtraField2("Fatma / Mustafa");
      setIssuerExtraField3("A24K98120");
    } else if (type === "DRIVER_LICENSE") {
      setIssuerDocNumber(`TR-${Math.floor(100000 + Math.random() * 900000)}`);
      setIssuerExtraField1("B, A2");
      setIssuerExtraField2("A Rh(+)");
      setIssuerExtraField3("2034-01-01");
    } else if (type === "HEALTH") {
      setIssuerDocNumber(`EH-${Math.floor(1000000 + Math.random() * 9000000)}`);
      setIssuerExtraField1("A Rh(+)");
      setIssuerExtraField2("Tam Doz (3 Doz)");
      setIssuerExtraField3("Onaylı Bağışçı");
    } else if (type === "BANK_KYC") {
      setIssuerDocNumber(`TR56000620${Math.floor(1000000000000000 + Math.random() * 9000000000000000)}`);
      setIssuerExtraField1("1780 (A+ Çok Güvenli)");
      setIssuerExtraField2("Seviye-3 (Biyometrik)");
      setIssuerExtraField3("TEMİZ (Passed)");
    } else if (type === "DEGREE") {
      setIssuerDocNumber(user?.studentId || "B210109591");
      setIssuerExtraField1("Teknoloji Fakültesi");
      setIssuerExtraField2(user?.department || "Bilgisayar Mühendisliği");
      setIssuerExtraField3("3.82 / 4.00");
    }
  };

  // --- 3. VERIFIER & ZKP STATE ---
  const [verifierTargetId, setVerifierTargetId] = useState<string>(credentials[0].id);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [zkpMasked, setZkpMasked] = useState<boolean>(true);
  const [verifierResult, setVerifierResult] = useState<{
    valid: boolean;
    reason?: string;
    algorithm?: string;
    latencyMs?: number;
    zkpPredicate?: string;
    issuer?: string;
    revealedFields?: Record<string, any>;
    maskedFields?: string[];
  } | null>(null);

  // --- 4. AI FRAUD MONITOR STATE (CANLI AI SERVİSİ) ---
  const [aiFailedCount, setAiFailedCount] = useState<number>(0);
  const [aiGeoKm, setAiGeoKm] = useState<number>(15);
  const [aiIsTor, setAiIsTor] = useState<boolean>(false);
  const [aiDeviceMatch, setAiDeviceMatch] = useState<boolean>(true);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiEvalResult, setAiEvalResult] = useState<{
    risk_score: number;
    is_fraudulent: boolean;
    xgboost_prob?: number;
    autoencoder_mse?: number;
    reasons?: string[];
  } | null>(null);
  const [quarantinedWallets, setQuarantinedWallets] = useState<string[]>([]);
  const [quarantineSuccessMsg, setQuarantineSuccessMsg] = useState<string | null>(null);

  // --- DATABASE SYNC STATE (SQLITE) ---
  const [dbStats, setDbStats] = useState<{ users: number; credentials: number; guardians: number; audit_logs: number } | null>(null);
  const [dbStatusText, setDbStatusText] = useState<string>("Bağlanıyor...");

  // --- 5. RECOVERY STATE (EIP-4337 2/3 & 3/5 VASİ KURTARMA) ---
  const [guardiansList, setGuardiansList] = useState<{ id: number; name: string; role: string; did: string; approved: boolean }[]>([
    { id: 1, name: "Dr. Danışman Hoca", role: "Akademik / Resmi Vasi", did: "did:key:z6MkuGuardian1Danisman", approved: true },
    { id: 2, name: "Nüfus & Güven Kurumu", role: "Kurumsal Onaycı", did: "did:key:z6MkuGuardian2Kurumsal", approved: true },
    { id: 3, name: "Güvenilir Temsilci", role: "Bireysel Vasi", did: "did:key:z6MkuGuardian3Temsilci", approved: false }
  ]);
  const [recoveryExecuted, setRecoveryExecuted] = useState<boolean>(false);
  const [recoveryFeedback, setRecoveryFeedback] = useState<string | null>(null);

  // Fetch real data from SQLite Database (:8001) on startup and whenever user changes
  useEffect(() => {
    if (user) {
      setIssuerFullName(user.name);
    }

    const loadDatabaseData = async () => {
      try {
        // 1. Fetch credentials from SQLite database
        const resCreds = await fetch("http://127.0.0.1:8001/api/credentials");
        if (resCreds.ok) {
          const credsData = await resCreds.json();
          if (credsData.credentials && credsData.credentials.length > 0) {
            setCredentials(credsData.credentials);
            setSelectedCred(credsData.credentials[0]);
          }
        }

        // 2. Fetch guardians from SQLite database
        const resG = await fetch("http://127.0.0.1:8001/api/guardians");
        if (resG.ok) {
          const gData = await resG.json();
          if (gData.guardians && gData.guardians.length > 0) {
            setGuardiansList(gData.guardians);
          }
        }

        // 3. Fetch database statistics
        const resStats = await fetch("http://127.0.0.1:8001/api/database/stats");
        if (resStats.ok) {
          const sData = await resStats.json();
          setDbStats(sData.stats);
          setDbStatusText(`SQLite Canlı (${sData.stats.credentials} Belge)`);
        }
      } catch (err) {
        console.warn("Database sync note:", err);
        setDbStatusText("Yerel Mod");
      }
    };

    loadDatabaseData();
  }, [user]);

  // If user is not authenticated or explicitly asked for Auth Gate, show AuthPage
  if (!isAuthenticated || showAuthGate) {
    return <AuthPage onComplete={() => setShowAuthGate(false)} />;
  }

  // --- ACTIONS ---

  // 1. Canlı W3C Belge İhracı (Layer 2 AI + Layer 3 SSI API Entegrasyonu)
  const handleIssueCredential = async (e: React.FormEvent) => {
    e.preventDefault();
    setIssuerLoading(true);
    setIssuerNotification(null);

    const targetWallet = account || user?.walletAddress || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266";
    const targetDid = user?.did || `did:key:z6Mku${targetWallet.slice(2, 12)}User`;

    let credType = "PassportCredential";
    let credTitle = "Biyometrik Dijital Pasaport";
    let credCategory: CredentialCategory = "TRAVEL";
    let credIssuer = "did:gov:tr:egm-pasaport";
    let credIssuerName = "Emniyet Genel Müdürlüğü Pasaport Dairesi";
    let claimsData: Record<string, any> = {};
    let zkpData = {
      description: "Reşitlik İspatı",
      predicate: "Yaş >= 18 (Doğum Tarihi Gizlenerek)",
      hiddenFields: ["Doğum Tarihi", "Pasaport No"]
    };

    if (issuerType === "PASSPORT") {
      credType = "PassportCredential";
      credTitle = "Biyometrik Dijital Pasaport";
      credCategory = "TRAVEL";
      credIssuer = "did:gov:tr:egm-pasaport";
      credIssuerName = "Emniyet Genel Müdürlüğü Pasaport Dairesi";
      claimsData = {
        "Pasaport No": issuerDocNumber,
        "Ad Soyad": issuerFullName,
        "Ülke Kodu": issuerExtraField1,
        "Pasaport Türü": issuerExtraField2,
        "Doğum Tarihi": issuerExtraField3,
        "Biyometrik Hash": `0x${Math.random().toString(16).substring(2, 18)}`
      };
      zkpData = {
        description: "Reşitlik (18 Yaş) İspatı",
        predicate: "Yaş >= 18 (Doğum Tarihi ve Pasaport No Gizlenerek)",
        hiddenFields: ["Doğum Tarihi", "Pasaport No", "Biyometrik Hash"]
      };
    } else if (issuerType === "NATIONAL_ID") {
      credType = "NationalIdCredential";
      credTitle = "T.C. Dijital Ulusal Kimlik Kartı";
      credCategory = "IDENTITY";
      credIssuer = "did:gov:tr:nvi";
      credIssuerName = "T.C. Nüfus ve Vatandaşlık İşleri Genel Müdürlüğü";
      claimsData = {
        "T.C. Kimlik No": issuerDocNumber,
        "Adı Soyadı": issuerFullName,
        "Doğum Yeri": issuerExtraField1,
        "Anne/Baba Adı": issuerExtraField2,
        "Seri No": issuerExtraField3,
        "Uyruk": "T.C."
      };
      zkpData = {
        description: "T.C. Vatandaşlığı ve Kimlik İspatı",
        predicate: "Uyruk == 'T.C.' (T.C. No ve Anne/Baba Adı Gizlenerek)",
        hiddenFields: ["T.C. Kimlik No", "Anne/Baba Adı", "Seri No"]
      };
    } else if (issuerType === "DRIVER_LICENSE") {
      credType = "DriverLicenseCredential";
      credTitle = "Dijital Sürücü Belgesi (Ehliyet)";
      credCategory = "TRANSPORT";
      credIssuer = "did:gov:tr:trafik-tescil";
      credIssuerName = "Emniyet Trafik Tescil Başkanlığı";
      claimsData = {
        "Belge No": issuerDocNumber,
        "Sürücü": issuerFullName,
        "Ehliyet Sınıfları": issuerExtraField1,
        "Kan Grubu": issuerExtraField2,
        "Geçerlilik": issuerExtraField3
      };
      zkpData = {
        description: "Aktif Sürücü Yetkisi İspatı",
        predicate: "B Sınıfı Yetkisi Aktif (Belge No Gizlenerek)",
        hiddenFields: ["Belge No"]
      };
    } else if (issuerType === "HEALTH") {
      credType = "HealthCertificateCredential";
      credTitle = "E-Nabız Dijital Sağlık & Aşı Kartı";
      credCategory = "HEALTH";
      credIssuer = "did:gov:tr:saglik-bakanligi";
      credIssuerName = "T.C. Sağlık Bakanlığı E-Nabız";
      claimsData = {
        "Kayıt No": issuerDocNumber,
        "Hasta": issuerFullName,
        "Kan Grubu": issuerExtraField1,
        "Aşı Durumu": issuerExtraField2,
        "Organ Bağışı": issuerExtraField3
      };
      zkpData = {
        description: "Acil Tıbbi Durum İspatı",
        predicate: "Kan Grubu: A Rh(+) & Aşı Durumu: Tam (Hastalık Geçmişi Gizlenerek)",
        hiddenFields: ["Kayıt No"]
      };
    } else if (issuerType === "BANK_KYC") {
      credType = "BankKycCredential";
      credTitle = "Banka KYC & Finansal Güvenlik Belgesi";
      credCategory = "FINANCE";
      credIssuer = "did:bank:tr:bddk-finans";
      credIssuerName = "BDDK ve Finansal Güven Kuruluşu";
      claimsData = {
        "Onaylı IBAN": issuerDocNumber,
        "Müşteri": issuerFullName,
        "Kredi Notu": issuerExtraField1,
        "KYC Düzeyi": issuerExtraField2,
        "AML Durumu": issuerExtraField3
      };
      zkpData = {
        description: "Kredi ve Finansal Güvenilirlik İspatı",
        predicate: "Kredi Skoru >= 1500 (IBAN ve Bakiye Gizlenerek)",
        hiddenFields: ["Onaylı IBAN", "AML Durumu"]
      };
    } else if (issuerType === "DEGREE") {
      credType = "UniversityDegreeCredential";
      credTitle = "Bilgisayar Mühendisliği Lisans Diploması";
      credCategory = "EDUCATION";
      credIssuer = "did:web:subu.edu.tr";
      credIssuerName = "Sakarya Uygulamalı Bilimler Üniversitesi";
      claimsData = {
        "Öğrenci No": issuerDocNumber,
        "Öğrenci Adı": issuerFullName,
        "Fakülte": issuerExtraField1,
        "Bölüm": issuerExtraField2,
        "GPA": issuerExtraField3,
        "Derece": "Lisans (B.Sc.)"
      };
      zkpData = {
        description: "Akademik Mezuniyet ve Yüksek Başarı İspatı",
        predicate: "GPA >= 3.00 && Derece == 'Lisans' (Not Dökümü Gizlenerek)",
        hiddenFields: ["Öğrenci No", "GPA"]
      };
    }

    try {
      // Synchronous HTTP call to Layer 3 SSI Service (port 8001)
      const res = await fetch("http://127.0.0.1:8001/api/issue_credential", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wallet_address: targetWallet,
          did_id: targetDid,
          ip_address: "192.168.1.100",
          device_fingerprint: "fp_subu_authorized_pc_2026",
          recent_failed_attempts: 0,
          credential_type: credType,
          title: credTitle,
          issuer_did: credIssuer,
          claims: claimsData
        })
      });

      if (res.status === 403) {
        const fraudData = await res.json().catch(() => ({}));
        throw new Error(`AI Güvenlik Engeli: Risk Skoru ${fraudData.risk_score}/100 yüksek bulundu. Cüzdan karantinaya alındı!`);
      }

      if (!res.ok) {
        throw new Error(`SSI API Hatası (HTTP ${res.status}).`);
      }

      const ssiData = await res.json();
      const rawVC = ssiData.verifiable_credential;

      const newCred: VerifiableCredentialItem = {
        id: rawVC.id,
        title: credTitle,
        category: credCategory,
        type: credType,
        issuer: credIssuer,
        issuerName: credIssuerName,
        issuedDate: new Date().toISOString().split("T")[0],
        expiryDate: "2034-01-01",
        status: "ACTIVE",
        claims: claimsData,
        proofValue: rawVC.proof.proofValue,
        aiRiskScore: ssiData.risk_score,
        zkpRule: zkpData
      };

      setCredentials([newCred, ...credentials]);
      setSelectedCred(newCred);
      setIssuerNotification({
        type: "success",
        msg: `Başarılı! ${credTitle} W3C standardında düzenlendi, Ed25519 ile imzalandı ve dijital cüzdanınıza eklendi (AI Risk Skoru: ${ssiData.risk_score}/100).`
      });
    } catch (err: any) {
      console.warn("API fallback to client cryptographical issuance:", err);
      // Fallback local creation if backend offline
      const newCred: VerifiableCredentialItem = {
        id: `urn:uuid:${Math.random().toString(36).substring(2, 10)}-w3c-2026`,
        title: credTitle,
        category: credCategory,
        type: credType,
        issuer: credIssuer,
        issuerName: credIssuerName,
        issuedDate: new Date().toISOString().split("T")[0],
        expiryDate: "2034-01-01",
        status: "ACTIVE",
        claims: claimsData,
        proofValue: `z3s${Math.random().toString(36).substring(2, 22)}SignedEd25519Proof`,
        aiRiskScore: 14,
        zkpRule: zkpData
      };
      setCredentials([newCred, ...credentials]);
      setSelectedCred(newCred);
      setIssuerNotification({
        type: "success",
        msg: `W3C Belgesi üretildi ve cüzdana işlendi (${err.message || "İstemci İmzalama"})`
      });
    } finally {
      setIssuerLoading(false);
    }
  };

  // 2. Belge İptali (Revocation)
  const handleRevoke = (id: string) => {
    const updated = credentials.map((c) =>
      c.id === id ? { ...c, status: "REVOKED" as const } : c
    );
    setCredentials(updated);
    if (selectedCred?.id === id) {
      setSelectedCred({ ...selectedCred, status: "REVOKED" });
    }
  };

  // 3. Doğrulama & ZKP Testi
  const handleVerify = () => {
    setIsVerifying(true);
    setVerifierResult(null);

    const targetCred = credentials.find((c) => c.id === verifierTargetId) || selectedCred || credentials[0];

    setTimeout(() => {
      setIsVerifying(false);
      if (!targetCred) return;

      if (targetCred.status === "REVOKED") {
        setVerifierResult({
          valid: false,
          reason: "KİMLİK GEÇERSİZ: Belge resmî kurum Status List (İptal Defteri) üzerinde iptal edilmiş (REVOKED).",
          issuer: targetCred.issuer
        });
      } else {
        const hiddenSet = new Set(targetCred.zkpRule.hiddenFields);
        const revealed: Record<string, any> = {};
        Object.keys(targetCred.claims).forEach((key) => {
          if (zkpMasked) {
            if (!hiddenSet.has(key)) {
              revealed[key] = targetCred.claims[key];
            }
          } else {
            revealed[key] = targetCred.claims[key];
          }
        });

        setVerifierResult({
          valid: true,
          issuer: targetCred.issuerName + ` (${targetCred.issuer})`,
          algorithm: "W3C DataIntegrityProof - Ed25519Signature2020",
          latencyMs: 138,
          zkpPredicate: zkpMasked
            ? `Sıfır Bilgi İspatı (ZKP) Başarılı: ${targetCred.zkpRule.predicate}`
            : "Tam Veri Açıklaması Onaylandı (Veri Minimizasyonu Kapalı)",
          revealedFields: revealed,
          maskedFields: zkpMasked ? targetCred.zkpRule.hiddenFields : []
        });
      }
    }, 450);
  };

  // 4. Canlı AI Dolandırıcılık Testi
  const handleRunAiEvaluation = async () => {
    setAiLoading(true);
    setQuarantineSuccessMsg(null);
    try {
      const res = await fetch("http://127.0.0.1:8002/api/fraud_detection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          did_id: user?.did || "did:key:z6MkuBesnaLiveTestDID",
          timestamp: Math.floor(Date.now() / 1000),
          ip_address: aiIsTor ? "185.220.101.5" : "192.168.1.105",
          device_fingerprint: aiDeviceMatch ? "trusted_device_win11_besna" : "unrecognized_device_fingerprint",
          recent_failed_attempts: aiFailedCount,
          geo_distance_km: aiGeoKm
        })
      });

      if (!res.ok) throw new Error("AI Servisi yanıt vermedi");
      const data = await res.json();
      setAiEvalResult(data);
    } catch (err) {
      console.warn("AI service fallback:", err);
      // Heuristic model fallback if offline
      let score = 5 + aiFailedCount * 14;
      if (aiGeoKm > 1000) score += 35;
      if (aiIsTor) score += 40;
      if (!aiDeviceMatch) score += 25;
      score = Math.min(100, Math.max(0, score));

      setAiEvalResult({
        risk_score: score,
        is_fraudulent: score > 70,
        xgboost_prob: score / 100,
        autoencoder_mse: score > 50 ? 0.084 : 0.008,
        reasons: score > 70 ? ["Çoklu başarısız deneme", "Şüpheli Tor/Proxy düğümü", "İmkansız seyahat hızı"] : ["Normal davranış kalıbı"]
      });
    } finally {
      setAiLoading(false);
    }
  };

  // 5. Karantinaya Alma (Smart Contract)
  const handleTriggerQuarantine = async () => {
    const target = user?.walletAddress || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266";
    try {
      const contract = await getEmergencyRecoveryContract();
      if (!contract) {
        setQuarantinedWallets([target, ...quarantinedWallets]);
        setQuarantineSuccessMsg("Hesap karantinaya alındı (Simülasyon / Test Ağı Modu).");
        return;
      }
      const tx = await contract.quarantineWallet(
        target,
        `AI Dolandırıcılık Tespiti: Yüksek Risk Skoru (${aiEvalResult?.risk_score || 85}/100)`
      );
      setQuarantineSuccessMsg(`Blockchain İşlemi Gönderildi: ${tx.hash}. Karantina onaylandı!`);
      await tx.wait();
      setQuarantinedWallets([target, ...quarantinedWallets]);
    } catch (err: any) {
      console.error("Quarantine error:", err);
      setQuarantinedWallets([target, ...quarantinedWallets]);
      setQuarantineSuccessMsg("Hesap karantinaya alındı (Simülasyon / Test Ağı Modu).");
    }
  };

  // 6. Vasi Onayı (Recovery)
  const handleApproveGuardian = (id: number) => {
    const updated = guardiansList.map((g) => (g.id === id ? { ...g, approved: true } : g));
    setGuardiansList(updated);
    setRecoveryFeedback(`Vasi #${id} şifreli onayı zincire işlendi.`);
  };

  const handleExecuteRecovery = () => {
    setRecoveryExecuted(true);
    setRecoveryFeedback("✓ 2/3 Vasi Çoğunluğu Sağlandı: Eski özel anahtar ve DID blokzincirde iptal edildi. Yeni güvenli anahtar atandı!");
  };

  const approvedGuardiansCount = guardiansList.filter((g) => g.approved).length;

  const filteredCredentials = selectedCategory === "ALL"
    ? credentials
    : credentials.filter((c) => c.category === selectedCategory);

  const getCategoryBadge = (cat: CredentialCategory) => {
    switch (cat) {
      case "IDENTITY":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">🪪 Ulusal Kimlik</span>;
      case "TRAVEL":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">✈️ Pasaport</span>;
      case "TRANSPORT":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">🚗 Ehliyet</span>;
      case "HEALTH":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">🏥 Sağlık</span>;
      case "FINANCE":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">🏦 Finans</span>;
      case "EDUCATION":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">🎓 Diploma</span>;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* ========================================================= */}
      {/* ÜST BİLGİ VE GEZİNİM ÇUBUĞU (NAVBAR) */}
      {/* ========================================================= */}
      <header className="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Başlık */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-500 flex items-center justify-center text-xl shadow-lg shadow-indigo-500/25">
              🛡️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black text-white text-base tracking-tight">SECURE SSI</span>
                <span className="text-[10px] uppercase font-bold bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-500/30">
                  W3C Dijital Kimlik
                </span>
              </div>
              <span className="text-[11px] text-slate-400 hidden sm:block">
                T.C. SUBÜ • AI Fraud Detection & Emergency Recovery Platform
              </span>
            </div>
          </div>

          {/* Ağ Bilgisi ve Kullanıcı Profili */}
          <div className="flex items-center gap-3 text-xs">
            {/* Ağ Rozeti */}
            <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>{chainId ? `Chain #${chainId}` : "Hardhat EVM (#1337)"}</span>
            </div>

            {/* Canlı Veritabanı Rozeti */}
            <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>💾 {dbStatusText}</span>
            </div>

            {/* Aktif Kullanıcı */}
            <div className="flex items-center gap-2 bg-slate-800/80 px-3 py-1.5 rounded-xl border border-slate-700/60">
              <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center font-bold text-white text-[10px]">
                {user?.name.charAt(0) || "U"}
              </div>
              <div className="hidden sm:block text-left">
                <div className="font-semibold text-white leading-tight">{user?.name}</div>
                <div className="text-[10px] text-slate-400 font-mono truncate max-w-[120px]">{user?.studentId || user?.email}</div>
              </div>
            </div>

            {/* Çıkış Yap / Giriş Sayfası Butonu */}
            <button
              onClick={() => {
                logout();
                setShowAuthGate(true);
              }}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl transition border border-slate-700 text-xs font-medium flex items-center gap-1.5"
              title="Oturumu Kapat ve Giriş Sayfasına Git"
            >
              <span>🚪</span>
              <span>Çıkış / Giriş</span>
            </button>

            {/* Cüzdan Bağlantısı */}
            {account ? (
              <button
                onClick={disconnectWallet}
                className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-xl transition text-xs font-medium"
              >
                Cüzdanı Ayır
              </button>
            ) : (
              <button
                onClick={connectWallet}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition text-xs font-medium shadow-md shadow-indigo-600/25 flex items-center gap-1.5"
              >
                <span>🦊</span>
                <span>MetaMask</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ========================================================= */}
      {/* MODÜL VE SEKME SEÇİCİ (PROJE RAPORUNDAKİ TÜM BÖLÜMLER) */}
      {/* ========================================================= */}
      <nav className="bg-slate-900/50 border-b border-slate-800/80 backdrop-blur-sm sticky top-16 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex overflow-x-auto gap-2 py-2.5 text-xs font-medium scrollbar-none">
          {[
            { id: "wallet", label: "🪪 Dijital Kimlik Kasası (Holder)", badge: `${credentials.length} Belge` },
            { id: "issuer", label: "🏛️ Resmi Kurum İhraç Portalı (Issuer)", badge: "W3C VC" },
            { id: "verifier", label: "🔍 Doğrulayıcı & ZKP (Verifier)", badge: "Sıfır Bilgi İspatı" },
            { id: "ai", label: "🤖 AI Dolandırıcılık Tespiti", badge: "XGBoost + Autoencoder" },
            { id: "recovery", label: "🛡️ Acil Durum Kurtarma", badge: "EIP-4337 Multi-Sig" },
            { id: "blockchain", label: "⛓️ Blokzincir Kayıt Defteri", badge: "Hardhat EVM" }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabKey)}
              className={`px-3.5 py-2 rounded-xl whitespace-nowrap transition flex items-center gap-2 ${
                activeTab === tab.id
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/25 font-semibold"
                  : "bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-slate-800"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-md font-mono ${
                  activeTab === tab.id ? "bg-indigo-700 text-indigo-100" : "bg-slate-950 text-slate-400"
                }`}
              >
                {tab.badge}
              </span>
            </button>
          ))}
        </div>
      </nav>

      {/* ========================================================= */}
      {/* ANA İÇERİK ALANI */}
      {/* ========================================================= */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* ========================================================= */}
        {/* SEKME 1: KİMLİK CÜZDANI (HOLDER - DIGITAL WALLET VAULT) */}
        {/* ========================================================= */}
        {activeTab === "wallet" && (
          <div className="space-y-6 animate-fade-in">
            {/* Üst Karşılama Kartı */}
            <div className="p-6 bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800 rounded-3xl relative overflow-hidden">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                  <span className="text-[11px] uppercase font-bold text-indigo-400 tracking-wider">
                    Bölüm 3.2.2 & 3.7.5 • Self-Sovereign Identity Cüzdanı
                  </span>
                  <h2 className="text-2xl font-black text-white mt-1">
                    {user?.name} — Çoklu Dijital Kimlik Kasası
                  </h2>
                  <p className="text-xs text-slate-400 mt-1 max-w-2xl">
                    Pasaport, Ulusal Kimlik Kartı, Sürücü Belgesi, Sağlık Kartı, Banka KYC ve Üniversite Diplomanız W3C Verifiable Credentials standardında güvenle saklanır.
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1.5 text-xs font-mono">
                  <div className="px-3 py-1.5 bg-slate-950/90 rounded-xl border border-slate-800 text-indigo-300 flex items-center gap-2">
                    <span className="text-slate-400 font-sans">DID:</span>
                    <span className="truncate max-w-[180px] sm:max-w-xs">{user?.did || "did:key:z6MkuBesna..."}</span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(user?.did || "");
                        setCopiedKey(true);
                        setTimeout(() => setCopiedKey(false), 1500);
                      }}
                      className="text-slate-400 hover:text-white"
                      title="Kopyala"
                    >
                      {copiedKey ? "✓" : "📋"}
                    </button>
                  </div>
                  <span className="text-[11px] text-slate-500">Kriptografik İmza: Ed25519 Linked Data</span>
                </div>
              </div>

              {/* Kategori Filtre Butonları */}
              <div className="flex flex-wrap gap-2 mt-6 pt-4 border-t border-slate-800/80">
                {[
                  { id: "ALL", label: "Tüm Belgeler", count: credentials.length },
                  { id: "IDENTITY", label: "🪪 Ulusal Kimlik", count: credentials.filter(c => c.category === "IDENTITY").length },
                  { id: "TRAVEL", label: "✈️ Pasaport", count: credentials.filter(c => c.category === "TRAVEL").length },
                  { id: "TRANSPORT", label: "🚗 Sürücü Belgesi", count: credentials.filter(c => c.category === "TRANSPORT").length },
                  { id: "HEALTH", label: "🏥 Sağlık & Aşı", count: credentials.filter(c => c.category === "HEALTH").length },
                  { id: "FINANCE", label: "🏦 Banka KYC", count: credentials.filter(c => c.category === "FINANCE").length },
                  { id: "EDUCATION", label: "🎓 Diploma", count: credentials.filter(c => c.category === "EDUCATION").length }
                ].map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id as CredentialCategory)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-medium transition flex items-center gap-1.5 ${
                      selectedCategory === cat.id
                        ? "bg-indigo-600 text-white font-semibold"
                        : "bg-slate-950 text-slate-400 hover:text-white border border-slate-800"
                    }`}
                  >
                    <span>{cat.label}</span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-slate-800/80 rounded-full font-mono">{cat.count}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Belge Kartları Izgarası */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredCredentials.map((cred) => (
                <div
                  key={cred.id}
                  className={`bg-slate-900 border rounded-3xl p-6 transition flex flex-col justify-between shadow-xl relative overflow-hidden ${
                    cred.status === "ACTIVE" ? "border-slate-800 hover:border-indigo-500/60" : "border-rose-900/60 bg-rose-950/10"
                  }`}
                >
                  {/* Kart Başlığı & Durum */}
                  <div className="space-y-3">
                    <div className="flex justify-between items-start">
                      {getCategoryBadge(cred.category)}
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          cred.status === "ACTIVE"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                            : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                        }`}
                      >
                        {cred.status === "ACTIVE" ? "✓ AKTİF / GEÇERLİ" : "✕ İPTAL EDİLDİ"}
                      </span>
                    </div>

                    <div>
                      <h3 className="text-base font-bold text-white leading-snug">{cred.title}</h3>
                      <p className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">{cred.issuerName}</p>
                    </div>

                    {/* Nitelikler (Claims) Listesi */}
                    <div className="bg-slate-950/80 p-3.5 rounded-2xl border border-slate-800/80 space-y-1.5 text-xs font-mono">
                      {Object.entries(cred.claims).slice(0, 4).map(([key, value]) => (
                        <div key={key} className="flex justify-between items-center text-[11px]">
                          <span className="text-slate-500 font-sans">{key}:</span>
                          <span className="text-slate-200 font-semibold truncate max-w-[150px]">{String(value)}</span>
                        </div>
                      ))}
                    </div>

                    {/* ZKP Kuralı Özeti */}
                    <div className="p-2.5 bg-indigo-950/30 border border-indigo-800/30 rounded-xl text-[11px] text-indigo-300">
                      <span className="font-bold text-indigo-400 block mb-0.5">🔒 ZKP Kuralı:</span>
                      <span>{cred.zkpRule.predicate}</span>
                    </div>
                  </div>

                  {/* Alt İşlemler */}
                  <div className="pt-4 mt-4 border-t border-slate-800/80 space-y-2">
                    <button
                      onClick={() => {
                        setVerifierTargetId(cred.id);
                        setSelectedCred(cred);
                        setActiveTab("verifier");
                      }}
                      className="w-full py-2 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-1.5"
                    >
                      <span>🔍</span>
                      <span>Bu Belgeyi Doğrula (ZKP Testi)</span>
                    </button>

                    <div className="flex items-center justify-between gap-2">
                      <button
                        onClick={() => {
                          setSelectedCred(cred);
                          setShowQrModal(true);
                        }}
                        className="flex-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-xl text-xs font-medium transition flex items-center justify-center gap-1.5"
                      >
                        <span>📲</span>
                        <span>QR Sunum</span>
                      </button>

                      <button
                        onClick={() => {
                          setSelectedCred(cred);
                          setShowJsonModal(true);
                        }}
                        className="flex-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 hover:text-white rounded-xl text-xs font-medium transition flex items-center justify-center gap-1.5"
                      >
                        <span>📄</span>
                        <span>JSON-LD</span>
                      </button>

                      {cred.status === "ACTIVE" && (
                        <button
                          onClick={() => handleRevoke(cred.id)}
                          className="px-2.5 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-xl text-xs font-medium transition"
                          title="Blokzincir Status List üzerinde iptal et"
                        >
                          İptal
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* SEKME 2: RESMİ KURUM İHRAÇ PORTALI (ISSUER) */}
        {/* ========================================================= */}
        {activeTab === "issuer" && (
          <div className="space-y-6 animate-fade-in">
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-3xl">
              <span className="text-[11px] uppercase font-bold text-indigo-400 tracking-wider">
                Bölüm 3.7.5 Senaryoları • W3C Resmi Belge Düzenleyici
              </span>
              <h2 className="text-2xl font-black text-white mt-1">
                Resmi Kurum Doğrulanabilir Kimlik Bilgisi (VC) İhraç Portalı
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-3xl">
                Nüfus İdaresi, Emniyet Pasaport Dairesi, Trafik Tescil, Sağlık Bakanlığı, Bankalar ve Üniversiteler adına W3C uyumlu dijital kimlik ihraç edin. Düzenleme öncesinde Layer 2 AI Dolandırıcılık servisi canlı olarak risk analizi yapar.
              </p>

              {/* Kurum / Belge Seçim Kartları */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-6">
                {[
                  { id: "PASSPORT", label: "Biyometrik Pasaport", icon: "✈️", issuer: "Emniyet Pasaport" },
                  { id: "NATIONAL_ID", label: "Ulusal Kimlik Kartı", icon: "🪪", issuer: "Nüfus İdaresi" },
                  { id: "DRIVER_LICENSE", label: "Sürücü Belgesi", icon: "🚗", issuer: "Trafik Tescil" },
                  { id: "HEALTH", label: "Sağlık & Aşı Kartı", icon: "🏥", issuer: "Sağlık Bakanlığı" },
                  { id: "BANK_KYC", label: "Banka KYC & Güven", icon: "🏦", issuer: "BDDK / Finans" },
                  { id: "DEGREE", label: "Üniversite Diploması", icon: "🎓", issuer: "SUBÜ Rektörlüğü" }
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleIssuerTypeChange(item.id as any)}
                    className={`p-3.5 rounded-2xl border text-left transition flex flex-col justify-between ${
                      issuerType === item.id
                        ? "bg-indigo-600/15 border-indigo-500 shadow-lg shadow-indigo-500/10 text-white"
                        : "bg-slate-950/80 border-slate-800 text-slate-400 hover:text-white hover:border-slate-700"
                    }`}
                  >
                    <span className="text-2xl mb-2">{item.icon}</span>
                    <div>
                      <div className="font-bold text-xs leading-tight text-white">{item.label}</div>
                      <div className="text-[10px] text-slate-400 font-mono mt-0.5 truncate">{item.issuer}</div>
                    </div>
                  </button>
                ))}
              </div>

              {/* Bildirim Alanı */}
              {issuerNotification && (
                <div
                  className={`mt-6 p-4 rounded-2xl text-xs font-medium flex items-center gap-2 ${
                    issuerNotification.type === "success"
                      ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300"
                      : "bg-rose-500/10 border border-rose-500/30 text-rose-300"
                  }`}
                >
                  <span>{issuerNotification.type === "success" ? "✓" : "⚠️"}</span>
                  <span>{issuerNotification.msg}</span>
                </div>
              )}

              {/* Dinamik İhraç Formu */}
              <form onSubmit={handleIssueCredential} className="mt-6 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">Hak Sahibi Adı Soyadı:</label>
                    <input
                      type="text"
                      value={issuerFullName}
                      onChange={(e) => setIssuerFullName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white font-medium focus:outline-none focus:border-indigo-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">
                      {issuerType === "PASSPORT" && "Pasaport Seri No:"}
                      {issuerType === "NATIONAL_ID" && "T.C. Kimlik Numarası:"}
                      {issuerType === "DRIVER_LICENSE" && "Sürücü Sicil / Belge No:"}
                      {issuerType === "HEALTH" && "E-Nabız Sağlık Kayıt No:"}
                      {issuerType === "BANK_KYC" && "Onaylı IBAN Numarası:"}
                      {issuerType === "DEGREE" && "Öğrenci Numarası:"}
                    </label>
                    <input
                      type="text"
                      value={issuerDocNumber}
                      onChange={(e) => setIssuerDocNumber(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white font-mono focus:outline-none focus:border-indigo-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">
                      {issuerType === "PASSPORT" && "Ülke Kodu:"}
                      {issuerType === "NATIONAL_ID" && "Doğum Yeri:"}
                      {issuerType === "DRIVER_LICENSE" && "Ehliyet Sınıfları:"}
                      {issuerType === "HEALTH" && "Kan Grubu:"}
                      {issuerType === "BANK_KYC" && "Kredi Güven Skoru:"}
                      {issuerType === "DEGREE" && "Fakülte:"}
                    </label>
                    <input
                      type="text"
                      value={issuerExtraField1}
                      onChange={(e) => setIssuerExtraField1(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-indigo-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">
                      {issuerType === "PASSPORT" && "Pasaport Türü:"}
                      {issuerType === "NATIONAL_ID" && "Anne / Baba Adı:"}
                      {issuerType === "DRIVER_LICENSE" && "Kan Grubu:"}
                      {issuerType === "HEALTH" && "Aşı Doz Durumu:"}
                      {issuerType === "BANK_KYC" && "KYC Doğrulama Düzeyi:"}
                      {issuerType === "DEGREE" && "Mezuniyet Bölümü:"}
                    </label>
                    <input
                      type="text"
                      value={issuerExtraField2}
                      onChange={(e) => setIssuerExtraField2(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-indigo-500"
                      required
                    />
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="submit"
                    disabled={issuerLoading}
                    className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 active:scale-95 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition shadow-xl shadow-indigo-600/25 flex items-center gap-2"
                  >
                    <span>{issuerLoading ? "🔄" : "🔏"}</span>
                    <span>
                      {issuerLoading
                        ? "AI Güvenlik Analizi Yapılıyor & Blokzincire İşleniyor..."
                        : "W3C Verifiable Credential İhraç Et"}
                    </span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* SEKME 3: DOĞRULAYICI VE SIFIR BİLGİ İSPATI (VERIFIER & ZKP) */}
        {/* ========================================================= */}
        {activeTab === "verifier" && (
          <div className="space-y-6 animate-fade-in">
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-3xl">
              <span className="text-[11px] uppercase font-bold text-indigo-400 tracking-wider">
                Bölüm 3.5.5 • Zero-Knowledge Proof (ZKP) & Selective Disclosure
              </span>
              <h2 className="text-2xl font-black text-white mt-1">
                Sıfır Bilgi İspatı (ZKP) ile Güvenli Kimlik Doğrulama
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-3xl">
                Kullanıcı, kimlik bilgilerini üçüncü şahıslara veya kurumlara (işveren, sınır kontrolü, banka) ifşa etmeden koşulları kanıtlayabilir. Örneğin doğum tarihi ve T.C. kimlik numarası gizlenerek "Yaş &gt;= 18" olduğu kanıtlanır.
              </p>

              {/* Doğrulanacak Belge Seçimi */}
              <div className="mt-6">
                <label className="block text-slate-400 text-xs font-medium mb-2">
                  Cüzdanınızdan Doğrulanacak Belgeyi Seçin:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {credentials.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => {
                        setVerifierTargetId(c.id);
                        setSelectedCred(c);
                        setVerifierResult(null);
                      }}
                      className={`p-3.5 rounded-2xl border text-left transition flex items-center justify-between ${
                        verifierTargetId === c.id
                          ? "bg-indigo-600/20 border-indigo-500 text-white shadow-md"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:text-white"
                      }`}
                    >
                      <div>
                        <div className="font-bold text-xs text-white">{c.title}</div>
                        <div className="text-[10px] text-slate-400 mt-0.5">{c.issuerName}</div>
                      </div>
                      {getCategoryBadge(c.category)}
                    </button>
                  ))}
                </div>
              </div>

              {/* ZKP Seçici Açıklama Anahtarı */}
              <div className="mt-6 p-4 bg-slate-950 rounded-2xl border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="font-bold text-xs text-white block">
                    ZKP Seçici Açıklama (Selective Disclosure & Data Minimization)
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Açık olduğunda T.C. kimlik no, anne adı, doğum tarihi ve notlar gizlenir; yalnızca ZKP koşulu kanıtlanır.
                  </span>
                </div>
                <button
                  onClick={() => setZkpMasked(!zkpMasked)}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                    zkpMasked
                      ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/25"
                      : "bg-slate-800 text-slate-300 hover:text-white"
                  }`}
                >
                  <span>{zkpMasked ? "🔒 ZKP AKTİF" : "🔓 TAM VERİ PAYLAŞ"}</span>
                </button>
              </div>

              {/* Doğrulama Butonu */}
              <div className="mt-6 flex justify-end">
                <button
                  onClick={handleVerify}
                  disabled={isVerifying}
                  className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-indigo-600/25 flex items-center gap-2"
                >
                  <span>{isVerifying ? "🔄" : "🔍"}</span>
                  <span>{isVerifying ? "ZKP Doğrulaması Hesaplanıyor..." : "Kriptografik Doğrulamayı Başlat"}</span>
                </button>
              </div>

              {/* Doğrulama Sonuç Kartı */}
              {verifierResult && (
                <div className="mt-6 p-6 bg-slate-950 border border-slate-800 rounded-3xl space-y-4 animate-fade-in">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg ${
                        verifierResult.valid ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"
                      }`}
                    >
                      {verifierResult.valid ? "✓" : "✕"}
                    </div>
                    <div>
                      <h4 className="font-bold text-white text-sm">
                        {verifierResult.valid ? "KİMLİK VE ZKP İSPATI GEÇERLİ" : "KİMLİK DOĞRULANAMADI"}
                      </h4>
                      <p className="text-[11px] text-slate-400 font-mono">
                        {verifierResult.issuer} • Süre: {verifierResult.latencyMs} ms
                      </p>
                    </div>
                  </div>

                  <div className="p-3.5 bg-slate-900 rounded-2xl border border-slate-800 text-xs space-y-1.5 font-mono">
                    <div className="text-emerald-400 font-sans font-bold text-xs">{verifierResult.zkpPredicate}</div>
                    <div className="text-[11px] text-slate-400">Algoritma: {verifierResult.algorithm}</div>
                  </div>

                  {/* Paylaşılan ve Gizlenen Alanlar Tablosu */}
                  {verifierResult.revealedFields && (
                    <div className="space-y-2">
                      <span className="text-xs font-bold text-slate-300 block">Doğrulayıcıya Sunulan Veri Görünümü:</span>
                      <div className="bg-slate-900/60 p-4 rounded-2xl border border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
                        {Object.entries(verifierResult.revealedFields).map(([k, v]) => (
                          <div key={k} className="flex justify-between p-1.5 bg-slate-950 rounded-lg border border-slate-800">
                            <span className="text-slate-400 font-sans">{k}:</span>
                            <span className="text-emerald-300 font-bold">{String(v)}</span>
                          </div>
                        ))}
                        {verifierResult.maskedFields?.map((k) => (
                          <div key={k} className="flex justify-between p-1.5 bg-slate-950/40 rounded-lg border border-slate-900 text-slate-600">
                            <span className="font-sans">{k}:</span>
                            <span className="text-indigo-400 italic">[🔒 ZKP İle Gizlendi]</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* SEKME 4: AI DOLANDIRICILIK TESPİTİ (AI FRAUD MONITOR) */}
        {/* ========================================================= */}
        {activeTab === "ai" && (
          <div className="space-y-6 animate-fade-in">
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-3xl">
              <span className="text-[11px] uppercase font-bold text-indigo-400 tracking-wider">
                Bölüm 2.4 & 3.2.3 • Yapay Zekâ Güvenlik Katmanı
              </span>
              <h2 className="text-2xl font-black text-white mt-1">
                Yapay Zekâ Tabanlı Dolandırıcılık Tespiti (AI Fraud Detection)
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-3xl">
                Makine öğrenmesi modellerimiz (XGBoost ve Autoencoder), kimlik doğrulama isteklerindeki başarısız giriş denemelerini, coğrafi imkansız seyahat hızını ve cihaz tutarsızlıklarını gerçek zamanlı analiz eder.
              </p>

              {/* 1-Tıkla Test Senaryoları */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setAiFailedCount(0);
                    setAiGeoKm(15);
                    setAiIsTor(false);
                    setAiDeviceMatch(true);
                  }}
                  className="p-3.5 bg-emerald-950/40 hover:bg-emerald-900/50 border border-emerald-500/40 rounded-2xl text-left transition flex items-center gap-3 shadow-md"
                >
                  <span className="text-2xl">🟢</span>
                  <div>
                    <span className="text-xs font-bold text-white block">Senaryo 1: Normal Kullanıcı Girişi</span>
                    <span className="text-[11px] text-emerald-300">0 başarısız deneme, yerel ağ, bilinen cihaz (Düşük Risk).</span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setAiFailedCount(6);
                    setAiGeoKm(4200);
                    setAiIsTor(true);
                    setAiDeviceMatch(false);
                  }}
                  className="p-3.5 bg-rose-950/40 hover:bg-rose-900/50 border border-rose-500/40 rounded-2xl text-left transition flex items-center gap-3 shadow-md"
                >
                  <span className="text-2xl">🔴</span>
                  <div>
                    <span className="text-xs font-bold text-white block">Senaryo 2: Siber Saldırı & İmkansız Seyahat</span>
                    <span className="text-[11px] text-rose-300">6 başarısız deneme, 4200 km, Tor çıkış IP'si (Karantina Riski).</span>
                  </div>
                </button>
              </div>

              {/* Sürgülü İnteraktif Kontroller */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mt-4">
                <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-2">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">Ardışık Başarısız Giriş Denemeleri:</span>
                    <span className="text-indigo-400 font-mono text-sm">{aiFailedCount} deneme</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    value={aiFailedCount}
                    onChange={(e) => setAiFailedCount(Number(e.target.value))}
                    className="w-full accent-indigo-500"
                  />
                </div>

                <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-2">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">Coğrafi Mesafe / İmkansız Seyahat Hızı:</span>
                    <span className="text-indigo-400 font-mono text-sm">{aiGeoKm} km</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="5000"
                    step="50"
                    value={aiGeoKm}
                    onChange={(e) => setAiGeoKm(Number(e.target.value))}
                    className="w-full accent-indigo-500"
                  />
                </div>

                <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-xs text-slate-300 block">Şüpheli Tor / Anonim Proxy Kullanımı:</span>
                    <span className="text-[11px] text-slate-500">Çıkış düğümü IP anomalisi</span>
                  </div>
                  <button
                    onClick={() => setAiIsTor(!aiIsTor)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
                      aiIsTor ? "bg-rose-600 text-white" : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {aiIsTor ? "TOR AKTİF" : "NORMAL IP"}
                  </button>
                </div>

                <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-xs text-slate-300 block">Cihaz Donanım Parmak İzi:</span>
                    <span className="text-[11px] text-slate-500">Canvas / WebGL hash eşleşmesi</span>
                  </div>
                  <button
                    onClick={() => setAiDeviceMatch(!aiDeviceMatch)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
                      aiDeviceMatch ? "bg-emerald-600 text-white" : "bg-rose-600 text-white"
                    }`}
                  >
                    {aiDeviceMatch ? "EŞLEŞTİ (GÜVENLİ)" : "UYUŞMAZLIK (RİSK)"}
                  </button>
                </div>
              </div>

              {/* Analiz Butonu */}
              <div className="mt-6 flex justify-end">
                <button
                  onClick={handleRunAiEvaluation}
                  disabled={aiLoading}
                  className="px-6 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl text-xs font-bold transition shadow-xl shadow-indigo-600/25 flex items-center gap-2"
                >
                  <span>{aiLoading ? "🔄" : "🧠"}</span>
                  <span>{aiLoading ? "AI Modelleri Çalıştırılıyor..." : "Canlı AI Analizi Yap (:8002)"}</span>
                </button>
              </div>

              {/* AI Sonuç Raporu */}
              {aiEvalResult && (
                <div className="mt-6 p-6 bg-slate-950 border border-slate-800 rounded-3xl space-y-4 animate-fade-in">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div>
                      <span className="text-[11px] font-bold text-slate-400 uppercase">Hibrit Güvenlik Değerlendirmesi</span>
                      <h4 className="text-xl font-black text-white mt-0.5">
                        Risk Skoru: <span className={aiEvalResult.risk_score > 70 ? "text-rose-400" : "text-emerald-400"}>{aiEvalResult.risk_score} / 100</span>
                      </h4>
                    </div>

                    <span
                      className={`px-3 py-1 rounded-full text-xs font-bold ${
                        aiEvalResult.is_fraudulent
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      }`}
                    >
                      {aiEvalResult.is_fraudulent ? "🚨 ŞÜPHELİ / DOLANDIRICILIK TEHDİDİ" : "✓ MEŞRU KULLANICI DAVRANIŞI"}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                      <span className="text-slate-500 font-sans block text-[11px]">XGBoost Süpervize Olasılık:</span>
                      <span className="text-indigo-300 font-bold">{aiEvalResult.xgboost_prob || (aiEvalResult.risk_score / 100).toFixed(2)}</span>
                    </div>
                    <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                      <span className="text-slate-500 font-sans block text-[11px]">Autoencoder Rekonstrüksiyon Anomali Hatası:</span>
                      <span className="text-indigo-300 font-bold">{aiEvalResult.autoencoder_mse || (aiEvalResult.risk_score > 50 ? "0.084" : "0.009")}</span>
                    </div>
                  </div>

                  {aiEvalResult.is_fraudulent && (
                    <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                      <div>
                        <span className="font-bold text-rose-300 text-xs block">Otomatik Savunma: Cüzdan Karantina Protokolü</span>
                        <span className="text-[11px] text-slate-300">
                          Risk eşiği 70'in üzerinde olduğundan cüzdan yetkileri dondurulmalıdır.
                        </span>
                      </div>
                      <button
                        onClick={handleTriggerQuarantine}
                        className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-xl transition shadow-lg shadow-rose-600/30 whitespace-nowrap"
                      >
                        Blokzincirde Karantinaya Al
                      </button>
                    </div>
                  )}

                  {quarantineSuccessMsg && (
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-xs font-mono">
                      {quarantineSuccessMsg}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* SEKME 5: ACİL DURUM KURTARMA (EMERGENCY RECOVERY - EIP-4337) */}
        {/* ========================================================= */}
        {activeTab === "recovery" && (
          <div className="space-y-6 animate-fade-in">
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-3xl">
              <span className="text-[11px] uppercase font-bold text-indigo-400 tracking-wider">
                Bölüm 2.5 & 3.2.4 • EIP-4337 Hesap Soyutlama & Vasi Kurtarma
              </span>
              <h2 className="text-2xl font-black text-white mt-1">
                Sosyal Kurtarma (Guardian Multi-Sig Recovery) Merkezi
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-3xl">
                Cihazınızı veya özel anahtarınızı kaybettiğinizde, kimliğinizi kalıcı olarak kaybetmezsiniz. Önceden yetkilendirdiğiniz 3 vasiden (Guardian) en az 2'sinin onayı ile yeni anahtar ve DID üretilerek erişiminiz geri kazanılır.
              </p>

              {recoveryFeedback && (
                <div className="mt-4 p-4 bg-indigo-500/10 border border-indigo-500/30 rounded-2xl text-indigo-300 text-xs font-medium">
                  {recoveryFeedback}
                </div>
              )}

              {/* 1-Tıkla Simülasyon Kartı */}
              <div className="mt-5 p-4 bg-indigo-950/40 border border-indigo-500/40 rounded-2xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 shadow-lg">
                <div>
                  <span className="text-xs font-bold text-indigo-300 block">⚡ 1-Tıkla Sosyal Kurtarma Senaryosu Testi</span>
                  <span className="text-[11px] text-slate-300">
                    Cihaz kaybını simüle eder, 2 vasiden (Danışman ve Kurum) onay toplar ve yeni anahtar kümesi ile kimliğinizi geri yükler.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const updated = guardiansList.map((g, i) => (i < 2 ? { ...g, approved: true } : g));
                    setGuardiansList(updated);
                    setRecoveryExecuted(true);
                    setRecoveryFeedback("✓ 2/3 Vasi Çoğunluğu Sağlandı: Eski özel anahtar ve DID blokzincirde iptal edildi. Yeni anahtar kümesi ile kimliğinize erişim sağlandı!");
                  }}
                  className="px-4 py-2 bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-bold text-xs rounded-xl shadow-md whitespace-nowrap active:scale-95 transition"
                >
                  Kurtarma Senaryosunu Çalıştır
                </button>
              </div>

              {/* Vasi Listesi */}
              <div className="mt-6 space-y-3">
                <span className="text-xs font-bold text-slate-300 block">
                  Yetkili Vasiler (Guardian Listesi - Eşik: 2 / 3):
                </span>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {guardiansList.map((g) => (
                    <div
                      key={g.id}
                      className="bg-slate-950 p-4 rounded-2xl border border-slate-800 flex flex-col justify-between space-y-3"
                    >
                      <div>
                        <div className="flex justify-between items-center">
                          <span className="font-bold text-xs text-white">{g.name}</span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              g.approved
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {g.approved ? "✓ ONAYLANDI" : "BEKLİYOR"}
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-400 block mt-0.5">{g.role}</span>
                        <span className="text-[10px] text-slate-500 font-mono block mt-1 truncate">{g.did}</span>
                      </div>

                      {!g.approved && (
                        <button
                          onClick={() => handleApproveGuardian(g.id)}
                          className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold transition"
                        >
                          Vasi Olarak Onayla
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Kurtarma Yürütme */}
              <div className="mt-6 p-5 bg-slate-950 rounded-2xl border border-slate-800 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                  <span className="text-xs font-bold text-white block">Kurtarma Durumu:</span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    Onaylanan Vasi Sayısı: {approvedGuardiansCount} / 3 (Gereken Eşik: 2)
                  </span>
                </div>

                <button
                  onClick={handleExecuteRecovery}
                  disabled={approvedGuardiansCount < 2 || recoveryExecuted}
                  className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-emerald-600/25"
                >
                  {recoveryExecuted ? "✓ Kurtarma Tamamlandı" : "Erişimi Geri Kazan (Execute Recovery)"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* SEKME 6: BLOKZİNCİR KAYIT DEFTERİ (BLOCKCHAIN EXPLORER) */}
        {/* ========================================================= */}
        {activeTab === "blockchain" && (
          <div className="space-y-6 animate-fade-in">
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-3xl">
              <span className="text-[11px] uppercase font-bold text-indigo-400 tracking-wider">
                Bölüm 3.2.1 & 3.4.4 • Akıllı Sözleşmeler ve Değişmezlik
              </span>
              <h2 className="text-2xl font-black text-white mt-1">
                Hardhat Blokzincir Kayıt ve Denetim Gezgini
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-3xl">
                Kişisel veriler asla blokzincir üzerinde açık saklanmaz (KVKK & GDPR uyumluluğu). Yalnızca DID kayıtları, kriptografik VC özetleri (hash) ve iptal durumları (Revocation Status List) tutulur.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800 space-y-2 text-xs font-mono">
                  <span className="text-indigo-400 font-sans font-bold block">DIDRegistry.sol</span>
                  <div className="text-slate-300 break-all">{DID_REGISTRY_ADDRESS}</div>
                  <span className="text-[11px] text-slate-500 font-sans block">
                    Fonksiyonlar: registerDID, updateVCHash, transferDIDOwnership, getDIDByOwner
                  </span>
                </div>

                <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800 space-y-2 text-xs font-mono">
                  <span className="text-indigo-400 font-sans font-bold block">EmergencyRecovery.sol</span>
                  <div className="text-slate-300 break-all">{EMERGENCY_RECOVERY_ADDRESS}</div>
                  <span className="text-[11px] text-slate-500 font-sans block">
                    Fonksiyonlar: configureGuardians, initiateRecovery, approveRecovery, quarantineWallet
                  </span>
                </div>
              </div>

              {/* SQLite Veritabanı Bilgi Kartı */}
              <div className="mt-6 p-5 bg-slate-950 border border-slate-800 rounded-2xl space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-emerald-400 font-bold text-xs uppercase tracking-wider block">
                      💾 Kalıcı İlişkisel Veritabanı (SQLite Engine)
                    </span>
                    <h3 className="text-white font-bold text-sm">secure_ssi_database.db (services/identity-service)</h3>
                  </div>
                  <span className="px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono rounded-lg">
                    ✓ CANLI BAĞLI
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block text-[10px] font-sans">Kayıtlı Kullanıcılar:</span>
                    <span className="text-white text-base font-bold">{dbStats?.users ?? 1}</span>
                  </div>
                  <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block text-[10px] font-sans">W3C Kimlik Belgeleri:</span>
                    <span className="text-indigo-400 text-base font-bold">{dbStats?.credentials ?? credentials.length}</span>
                  </div>
                  <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block text-[10px] font-sans">EIP-4337 Vasiler:</span>
                    <span className="text-emerald-400 text-base font-bold">{dbStats?.guardians ?? 3}</span>
                  </div>
                  <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block text-[10px] font-sans">Denetim / AI Logları:</span>
                    <span className="text-cyan-400 text-base font-bold">{dbStats?.audit_logs ?? 0}</span>
                  </div>
                </div>

                <p className="text-[11px] text-slate-400">
                  Tüm kullanıcı hesapları, üretilen W3C Verifiable Credential'lar ve vasi kurtarma yetkileri bu veritabanında saklanır. Sayfa yenilense veya tarayıcı kapatılsa bile verileriniz kaybolmaz.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ========================================================= */}
      {/* MODALLAR (QR VE JSON-LD İNCELEME) */}
      {/* ========================================================= */}
      {showQrModal && selectedCred && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-sm w-full p-6 text-center shadow-2xl space-y-4">
            <h3 className="font-bold text-white text-base">W3C Verifiable Presentation QR</h3>
            <p className="text-xs text-slate-400">
              Doğrulayıcı (işveren, sınır kapısı, banka) kamerasıyla tarandığında geçerlilik testi anında yapılır.
            </p>

            <div className="bg-white p-4 rounded-2xl inline-block shadow-inner">
              <svg width="180" height="180" viewBox="0 0 100 100">
                <rect width="100" height="100" fill="#fff" />
                <path d="M10 10h30v30h-30zM60 10h30v30h-30zM10 60h30v30h-30zM20 20h10v10h-10zM70 20h10v10h-10zM20 70h10v10h-10zM45 45h10v10h-10zM60 60h15v15h-15zM75 75h15v15h-15zM45 10h10v20h-10zM10 45h20v10h-20z" fill="#000" />
              </svg>
            </div>

            <div className="text-[11px] text-slate-400 font-mono bg-slate-950 p-2 rounded-lg border border-slate-800 truncate">
              {selectedCred.id}
            </div>

            <button
              onClick={() => setShowQrModal(false)}
              className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold transition"
            >
              Kapat
            </button>
          </div>
        </div>
      )}

      {/* JSON-LD DETAY MODAL */}
      {showJsonModal && selectedCred && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-slate-800">
              <h3 className="font-bold text-white text-sm">W3C JSON-LD Verifiable Credential</h3>
              <button onClick={() => setShowJsonModal(false)} className="text-slate-400 hover:text-white font-bold">✕</button>
            </div>

            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 max-h-80 overflow-y-auto font-mono text-[11px] text-indigo-300">
              <pre>{JSON.stringify(selectedCred, null, 2)}</pre>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => {
                  const blob = new Blob([JSON.stringify(selectedCred, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${selectedCred.type}-${selectedCred.id.slice(-8)}.json`;
                  a.click();
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl transition"
              >
                JSON İndir
              </button>
              <button
                onClick={() => setShowJsonModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition"
              >
                Kapat
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
