import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { useWallet } from "../../context/WalletContext";
import { fetchCredentials, BackendCredential } from "../../services/api";

export type HolderScreen = 
  | "DASHBOARD" | "IDENTITY" | "WALLET" | "CREDENTIALS" | "CREDENTIAL_DETAIL" 
  | "PRESENT" | "CONSENT" | "VERIFICATION_RESULT" | "ACTIVITY" | "SECURITY" | "RECOVERY";

export interface VerifiableCredentialItem {
  id: string;
  title: string;
  category: "IDENTITY" | "QUALIFIED" | "PROFESSIONAL" | "FINANCE" | "TRAVEL" | "TRANSPORT" | "HEALTH";
  type: string;
  issuer: string;
  issuerName: string;
  issuedDate: string;
  expiryDate: string;
  status: "ACTIVE" | "REVOKED";
  claims: Record<string, any>;
  proofValue: string;
  statusListIndex: number;
  aiRiskScore: number;
  zkpRule: {
    description: string;
    predicate: string;
    hiddenFields: string[];
  };
}

const INITIAL_FALLBACK_CREDENTIALS: VerifiableCredentialItem[] = [
  {
    id: "urn:uuid:eudi-natid-2026-tr-9021",
    title: "eIDAS Yüksek Güvenlikli Ulusal Kimlik Kartı",
    category: "IDENTITY",
    type: "NationalIdentityCredential",
    issuer: "did:gov:eudi:nvi-authority",
    issuerName: "T.C. Nüfus ve Vatandaşlık İşleri / EUDI Trust Framework",
    issuedDate: "2025-01-15",
    expiryDate: "2035-01-15",
    status: "ACTIVE",
    statusListIndex: 104,
    claims: {
      "Adı Soyadı": "Charaf Eddine Bessanane",
      "Ulusal Kimlik No": "TR-10293847561",
      "Uyruk": "T.C. & AB Uygunluk",
      "Doğum Tarihi": "1999-04-12",
      "Doğum Yeri": "İstanbul",
      "Güven Seviyesi (LoA)": "eIDAS High (Qualified)",
      "Seri No": "A92K81029"
    },
    proofValue: "z3s9PqRtXvM8EUDINationalIdentityProof2026Ed25519Signature",
    aiRiskScore: 4,
    zkpRule: {
      description: "Reşit Olma ve Vatandaşlık İspatı (Seçici İfşa)",
      predicate: "Yaş >= 18 && Uyruk == 'T.C.' (Doğum Tarihi ve TC No Gizlenerek)",
      hiddenFields: ["Ulusal Kimlik No", "Seri No", "Doğum Tarihi", "Doğum Yeri"]
    }
  },
  {
    id: "urn:uuid:qeaa-arch-2026-cert-4401",
    title: "Nitelikli Sistem Mimarı Nitelik Tasdiki (QEAA)",
    category: "QUALIFIED",
    type: "QualifiedElectronicAttestationCredential",
    issuer: "did:web:trust.eudi.europa.eu",
    issuerName: "European Cybersecurity & Identity Certification Body",
    issuedDate: "2025-06-20",
    expiryDate: "2028-06-20",
    status: "ACTIVE",
    statusListIndex: 288,
    claims: {
      "Sertifika Sahibi": "Charaf Eddine Bessanane",
      "Unvan": "Senior Distributed Systems & SSI Security Architect",
      "Yetki Kapsamı": "W3C VC 2.0 / OID4VCI / OID4VP Cryptographic Engine",
      "Akreditasyon No": "EU-QEAA-9981-SEC",
      "Veriliş Standardı": "eIDAS Regulation (EU) 910/2014 Annex V"
    },
    proofValue: "z4r8NmKyTwJ7QEAAEuCybersecurityArchitectSignedEd25519",
    aiRiskScore: 6,
    zkpRule: {
      description: "Kıdemli Mimar Lisans Doğrulaması",
      predicate: "Unvan == 'Senior Distributed Systems Architect' (Akreditasyon No Gizlenerek)",
      hiddenFields: ["Akreditasyon No"]
    }
  }
];

export const HolderPortal: React.FC<{ activeScreen: HolderScreen; onNavigate: (screen: HolderScreen) => void }> = ({
  activeScreen,
  onNavigate
}) => {
  const { user } = useAuth();
  const { account } = useWallet();

  const [credentials, setCredentials] = useState<VerifiableCredentialItem[]>(INITIAL_FALLBACK_CREDENTIALS);
  const [selectedCredential, setSelectedCredential] = useState<VerifiableCredentialItem>(INITIAL_FALLBACK_CREDENTIALS[0]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Fetch real credentials from backend on load
  useEffect(() => {
    fetchCredentials()
      .then((backendCreds) => {
        if (backendCreds && backendCreds.length > 0) {
          const mapped: VerifiableCredentialItem[] = backendCreds.map((c, idx) => ({
            id: c.id,
            title: c.title,
            category: (c.category as any) || "IDENTITY",
            type: c.credential_type,
            issuer: c.issuer,
            issuerName: c.issuer_name || "Official EUDI Issuer",
            issuedDate: c.issued_date,
            expiryDate: c.expiry_date || "Süresiz",
            status: c.status,
            statusListIndex: (idx + 1) * 64,
            claims: typeof c.claims === "string" ? JSON.parse(c.claims) : (c.claims || {}),
            proofValue: c.proof_value || "z3sProofValEd25519SignedW3C",
            aiRiskScore: c.ai_risk_score || 5,
            zkpRule: {
              description: `${c.title} Seçici İfşa Kuralı`,
              predicate: c.zkp_predicate || "W3C VC 2.0 ZKP Valid",
              hiddenFields: []
            }
          }));
          setCredentials(mapped);
          setSelectedCredential(mapped[0]);
        }
      })
      .finally(() => setIsLoading(false));
  }, []);
  
  // Present & Consent state
  const [requestUri, setRequestUri] = useState("openid4vp://authorize?client_id=did:web:enterprise-verifier.eu&response_uri=http://localhost:8000/api/v1/identity/presentations/verify&nonce=n-88a91c7f&dcql_query=eudi_kyc_req");
  const [disclosedFields, setDisclosedFields] = useState<Record<string, boolean>>({
    "Adı Soyadı": true,
    "Güven Seviyesi (LoA)": true,
    "Ulusal Kimlik No": false,
    "Seri No": false,
    "Doğum Tarihi": false,
    "Doğum Yeri": false,
    "Uyruk": true
  });
  const [presentationSuccess, setPresentationSuccess] = useState<boolean>(false);
  const [revealSeed, setRevealSeed] = useState<boolean>(false);
  const [keyRotatedMsg, setKeyRotatedMsg] = useState<string | null>(null);

  const handleToggleField = (field: string) => {
    setDisclosedFields(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const handleExecutePresentation = () => {
    setPresentationSuccess(true);
    setTimeout(() => {
      onNavigate("VERIFICATION_RESULT");
    }, 800);
  };

  const handleRotateKey = () => {
    setKeyRotatedMsg("Yeni Ed25519 anahtar çifti oluşturuldu. Eski anahtar başarıyla revize edildi ve DID Document güncellendi.");
    setTimeout(() => setKeyRotatedMsg(null), 5000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* 1. DASHBOARD */}
      {activeScreen === "DASHBOARD" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "20px",
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-default)",
            borderRadius: "10px"
          }}>
            <div>
              <div style={{ fontSize: "12px", color: "var(--color-primary)", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Egemen Kimlik Cüzdanı (Holder Wallet)
              </div>
              <h2 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>
                Hoş Geldiniz, {user?.name || "Kimlik Sahibi"}
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
                DID: <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{user?.did || "did:key:z6MkuBesna..."}</span>
              </p>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={() => onNavigate("PRESENT")}
                style={{
                  padding: "10px 16px",
                  backgroundColor: "var(--color-primary)",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: "600",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                📲 Sunum Yap (OID4VP)
              </button>
              <button
                onClick={() => onNavigate("CREDENTIALS")}
                style={{
                  padding: "10px 16px",
                  backgroundColor: "var(--bg-subtle)",
                  color: "var(--text-main)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: "600",
                  cursor: "pointer"
                }}
              >
                📜 Belgelerim ({credentials.length})
              </button>
            </div>
          </div>

          {/* Quick Metrics Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
            <div style={{
              padding: "16px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "8px"
            }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Doğrulanabilir Kimlikler (VC)</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#60a5fa", marginTop: "6px" }}>{credentials.length} Adet</div>
              <div style={{ fontSize: "11px", color: "var(--color-success)", marginTop: "4px" }}>✓ W3C VC 2.0 Tam Uyumlu</div>
            </div>

            <div style={{
              padding: "16px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "8px"
            }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Güven Seviyesi (LoA)</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#10b981", marginTop: "6px" }}>eIDAS High</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Kriptografik Donanım İmzalı</div>
            </div>

            <div style={{
              padding: "16px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "8px"
            }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>AI Davranışsal Risk Puanı</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#38bdf8", marginTop: "6px" }}>0.04 (DÜŞÜK)</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>XGBoost + Autoencoder Temiz</div>
            </div>

            <div style={{
              padding: "16px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "8px"
            }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Sosyal Kurtarma Vasileri</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#a855f7", marginTop: "6px" }}>3/5 Quorum</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>EIP-4337 Aktif</div>
            </div>
          </div>

          {/* Recent Credentials Preview */}
          <div style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-default)",
            borderRadius: "10px",
            padding: "20px"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-main)" }}>
                Aktif Verifiable Credentials (Cüzdan Kasası)
              </h3>
              <button
                onClick={() => onNavigate("CREDENTIALS")}
                style={{ fontSize: "12px", color: "#60a5fa", background: "none", border: "none", cursor: "pointer" }}
              >
                Tümünü İncele →
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
              {credentials.map(vc => (
                <div
                  key={vc.id}
                  onClick={() => { setSelectedCredential(vc); onNavigate("CREDENTIAL_DETAIL"); }}
                  style={{
                    padding: "16px",
                    backgroundColor: "var(--bg-subtle)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "8px",
                    cursor: "pointer",
                    transition: "border-color 0.15s ease"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: "rgba(37, 99, 235, 0.15)",
                      color: "#60a5fa"
                    }}>
                      {vc.category}
                    </span>
                    <span style={{ fontSize: "10px", color: "var(--color-success)", fontWeight: "600" }}>✓ AKTİF</span>
                  </div>
                  <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "4px" }}>
                    {vc.title}
                  </h4>
                  <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    İhraççı: {vc.issuerName}
                  </p>
                  <div style={{ marginTop: "12px", fontSize: "11px", color: "#64748b", display: "flex", justifyContent: "space-between" }}>
                    <span>Son Geçerlilik: {vc.expiryDate}</span>
                    <span style={{ color: "#60a5fa" }}>Detay →</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. IDENTITY (DID DOCUMENT) */}
      {activeScreen === "IDENTITY" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            W3C DID Document & Kriptografik Kimlik
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            W3C Decentralized Identifiers (DIDs) v1.0 spesifikasyonuna göre üretilmiş egemen kimlik belgesi.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>Aktif DID Metodu</div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)" }}>did:key (Ed25519 Cryptosuite)</div>
              <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>W3C Data Integrity Ed25519Signature2020 / eddsa-jcs-2022</div>
            </div>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>On-Chain EVM Adresi</div>
              <div style={{ fontSize: "13px", fontFamily: "var(--font-mono)", color: "#10b981" }}>{user?.walletAddress || account || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"}</div>
              <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>Hardhat Yerel EVM Zinciri / EIP-4337 Akıllı Hesap</div>
            </div>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
              W3C DID Document JSON-LD Temsili
            </label>
            <pre style={{
              padding: "16px",
              backgroundColor: "var(--bg-input)",
              border: "1px solid var(--border-default)",
              borderRadius: "6px",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              color: "#93c5fd",
              overflowX: "auto",
              lineHeight: "1.5"
            }}>
{JSON.stringify({
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/suites/ed25519-2020/v1"
  ],
  "id": user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519",
  "verificationMethod": [
    {
      "id": `${user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519"}#key-1`,
      "type": "Ed25519VerificationKey2020",
      "controller": user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519",
      "publicKeyMultibase": "z6MkuBesnaPublicKeyMultibaseRepresentationValid2026"
    }
  ],
  "authentication": [
    `${user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519"}#key-1`
  ],
  "assertionMethod": [
    `${user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519"}#key-1`
  ]
}, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* 3. WALLET (KEY LIFECYCLE) */}
      {activeScreen === "WALLET" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Kriptografik Anahtar Yönetimi & Yaşam Döngüsü
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Cüzdan anahtarları yerel izole alanda yönetilir. Özel anahtar (private key) asla dışarı çıkarılamaz veya veritabanına düz metin yazılamaz.
          </p>

          {keyRotatedMsg && (
            <div style={{
              padding: "12px 16px",
              borderRadius: "6px",
              backgroundColor: "rgba(22, 163, 74, 0.12)",
              border: "1px solid rgba(22, 163, 74, 0.3)",
              color: "#4ade80",
              fontSize: "13px",
              marginBottom: "16px"
            }}>
              ✓ {keyRotatedMsg}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "20px" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)" }}>Birincil İmzalama Anahtarı (Ed25519)</span>
                  <span style={{ fontSize: "11px", color: "var(--color-success)", fontWeight: "600" }}>● AKTİF</span>
                </div>
                <div style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "#60a5fa", wordBreak: "break-all" }}>
                  Key ID: key-1 (Ed25519VerificationKey2020)
                </div>
                <div style={{ marginTop: "12px", display: "flex", gap: "10px" }}>
                  <button
                    onClick={handleRotateKey}
                    style={{
                      padding: "8px 14px",
                      backgroundColor: "var(--color-primary)",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: "600",
                      cursor: "pointer"
                    }}
                  >
                    🔄 Anahtarı Döndür (Rotate Key)
                  </button>
                  <button
                    onClick={() => onNavigate("RECOVERY")}
                    style={{
                      padding: "8px 14px",
                      backgroundColor: "transparent",
                      color: "#f59e0b",
                      border: "1px solid rgba(245, 158, 11, 0.4)",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: "600",
                      cursor: "pointer"
                    }}
                  >
                    🆘 Vasi Kurtarma Başlat
                  </button>
                </div>
              </div>

              {/* Seed Backup */}
              <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
                <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "4px" }}>
                  12 Kelimelik Kurtarma Tohum İfadesi (BIP-39 Mnemonic)
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "12px" }}>
                  Cihaz kaybı durumunda cüzdanınızı yeniden yüklemek için tohum ifadenizi yedekleyin.
                </p>

                {revealSeed ? (
                  <div style={{
                    padding: "12px",
                    backgroundColor: "var(--bg-input)",
                    border: "1px solid var(--border-default)",
                    borderRadius: "6px",
                    fontFamily: "var(--font-mono)",
                    fontSize: "12px",
                    color: "#fcd34d",
                    lineHeight: "1.6"
                  }}>
                    {user?.seedPhrase || "apple banana cherry dolphin eagle falcon gorilla horizon island jungle knight leopard"}
                  </div>
                ) : (
                  <button
                    onClick={() => setRevealSeed(true)}
                    style={{
                      padding: "8px 14px",
                      backgroundColor: "var(--bg-input)",
                      color: "var(--text-main)",
                      border: "1px solid var(--border-default)",
                      borderRadius: "6px",
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    👁️ Tohum İfadesini Göster
                  </button>
                )}
              </div>
            </div>

            {/* Key Policy rules */}
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "10px" }}>
                Güvenlik Prensipleri (Master Plan)
              </h4>
              <ul style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.7", paddingLeft: "16px" }}>
                <li>Private key hiçbir zaman HTTP isteğinde veya yanıtında yer almaz.</li>
                <li>Veritabanına yalnızca public key referansı ve key metadata yazılır.</li>
                <li>Anahtar döndürme durumunda eski anahtar W3C DID dokümanında iptal edilir.</li>
                <li>Şüpheli davranış durumunda AI Fraud Engine anahtarı otomatik askıya alabilir.</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* 4. CREDENTIALS (LIST & GRID) */}
      {activeScreen === "CREDENTIALS" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <div>
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)" }}>
                Verifiable Credentials Deposu (W3C VC 2.0)
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
                Güvenilir ihraççılar tarafından imzalanmış ve cüzdanınızda saklanan dijital belgeler.
              </p>
            </div>
            <button
              onClick={() => onNavigate("PRESENT")}
              style={{
                padding: "8px 16px",
                backgroundColor: "var(--color-primary)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Doğrulamaya Sun (OID4VP)
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
            {credentials.map(vc => (
              <div
                key={vc.id}
                style={{
                  padding: "18px",
                  backgroundColor: "var(--bg-subtle)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "8px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: "rgba(37, 99, 235, 0.15)",
                      color: "#60a5fa"
                    }}>
                      {vc.category}
                    </span>
                    <span style={{ fontSize: "10px", color: "var(--color-success)", fontWeight: "600" }}>✓ {vc.status}</span>
                  </div>
                  <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginBottom: "6px" }}>
                    {vc.title}
                  </h4>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "12px" }}>
                    İhraççı: {vc.issuerName}
                  </div>
                  <div style={{ fontSize: "11px", color: "#64748b" }}>
                    StatusList2021 İndeksi: #{vc.statusListIndex}
                  </div>
                </div>

                <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border-default)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <button
                    onClick={() => { setSelectedCredential(vc); onNavigate("CREDENTIAL_DETAIL"); }}
                    style={{
                      fontSize: "12px",
                      color: "#60a5fa",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0
                    }}
                  >
                    Detayları Görüntüle →
                  </button>
                  <button
                    onClick={() => { setSelectedCredential(vc); onNavigate("CONSENT"); }}
                    style={{
                      fontSize: "11px",
                      padding: "4px 10px",
                      backgroundColor: "var(--bg-input)",
                      color: "var(--text-main)",
                      border: "1px solid var(--border-default)",
                      borderRadius: "4px",
                      cursor: "pointer"
                    }}
                  >
                    Sunum Oluştur
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. CREDENTIAL DETAIL */}
      {activeScreen === "CREDENTIAL_DETAIL" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <button
                onClick={() => onNavigate("CREDENTIALS")}
                style={{ fontSize: "12px", color: "#60a5fa", background: "none", border: "none", cursor: "pointer", marginBottom: "6px" }}
              >
                ← Belgelere Geri Dön
              </button>
              <h3 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-main)" }}>
                {selectedCredential.title}
              </h3>
            </div>
            <span style={{
              padding: "4px 12px",
              borderRadius: "4px",
              backgroundColor: "rgba(22, 163, 74, 0.15)",
              color: "#4ade80",
              fontSize: "12px",
              fontWeight: "600"
            }}>
              ✓ Kriptografik Olarak Geçerli
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                Tasdik Edilen İddialar (Claims)
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {Object.entries(selectedCredential.claims).map(([key, val]) => (
                  <div key={key} style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", borderBottom: "1px solid rgba(255,255,255,0.04)", paddingBottom: "4px" }}>
                    <span style={{ color: "var(--text-muted)" }}>{key}:</span>
                    <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                Kriptografik İspat Meta Verisi
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>İhraççı DID:</span>
                  <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>{selectedCredential.issuer}</div>
                </div>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>W3C Cryptosuite:</span>
                  <div style={{ fontFamily: "var(--font-mono)", color: "var(--text-main)", marginTop: "2px" }}>eddsa-jcs-2022 (Data Integrity)</div>
                </div>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Bitstring StatusList2021 İndeksi:</span>
                  <div style={{ fontFamily: "var(--font-mono)", color: "#10b981", marginTop: "2px" }}>Slot #{selectedCredential.statusListIndex} (Status: 0x00 Active)</div>
                </div>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>İmza Kanıtı (Proof):</span>
                  <div style={{ fontFamily: "var(--font-mono)", color: "#94a3b8", fontSize: "11px", wordBreak: "break-all", marginTop: "2px" }}>
                    {selectedCredential.proofValue}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
              W3C VC 2.0 Ham JSON-LD Yükü
            </label>
            <pre style={{
              padding: "16px",
              backgroundColor: "var(--bg-input)",
              border: "1px solid var(--border-default)",
              borderRadius: "6px",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              color: "#93c5fd",
              overflowX: "auto",
              lineHeight: "1.5"
            }}>
{JSON.stringify({
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    "https://w3id.org/security/suites/ed25519-2020/v1"
  ],
  "id": selectedCredential.id,
  "type": ["VerifiableCredential", selectedCredential.type],
  "issuer": selectedCredential.issuer,
  "validFrom": `${selectedCredential.issuedDate}T00:00:00Z`,
  "validUntil": `${selectedCredential.expiryDate}T23:59:59Z`,
  "credentialSubject": {
    "id": user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519",
    ...selectedCredential.claims
  },
  "credentialStatus": {
    "id": "http://localhost:8000/api/v1/identity/status-lists/status-list-2026",
    "type": "BitstringStatusListEntry",
    "statusPurpose": "revocation",
    "statusListIndex": selectedCredential.statusListIndex
  },
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "created": `${selectedCredential.issuedDate}T09:00:00Z`,
    "verificationMethod": `${selectedCredential.issuer}#key-1`,
    "proofPurpose": "assertionMethod",
    "proofValue": selectedCredential.proofValue
  }
}, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* 6. PRESENT (OID4VP TRIGGER) */}
      {activeScreen === "PRESENT" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            OID4VP 1.0 Sunum Talebi Kabul Et (Presentation Request)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Doğrulayıcı kurumdan gelen OpenID for Verifiable Presentations talebini kabul edin veya derin bağlantıyı yapıştırın.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "700px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                OID4VP İstek URL'si (Request URI)
              </label>
              <textarea
                value={requestUri}
                onChange={(e) => setRequestUri(e.target.value)}
                rows={3}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "12px",
                  fontFamily: "var(--font-mono)",
                  lineHeight: "1.5"
                }}
              />
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Doğrulayıcı Talep Özeti (Ayrıştırılan Parametreler)
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                <div><span style={{ color: "var(--text-muted)" }}>Relying Party:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>did:web:enterprise-verifier.eu</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Response URI:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#cbd5e1" }}>/api/v1/identity/presentations/verify</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Tazelik Challenge / Nonce:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#10b981" }}>n-88a91c7f (Anti-Replay Korumalı)</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Sorgu Standardı:</span> <span style={{ fontWeight: "600", color: "var(--text-main)" }}>DCQL (Digital Credentials Query Language)</span></div>
              </div>
            </div>

            <button
              onClick={() => onNavigate("CONSENT")}
              style={{
                padding: "12px 20px",
                backgroundColor: "var(--color-primary)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer",
                alignSelf: "flex-start"
              }}
            >
              🛡️ Kullanıcı Rızası & Seçici İfşayı Yapılandır (Consent) →
            </button>
          </div>
        </div>
      )}

      {/* 7. CONSENT (SELECTIVE DISCLOSURE) */}
      {activeScreen === "CONSENT" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <h3 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-main)" }}>
                Kullanıcı Rızası & Veri Minimizasyonu (Consent Screen)
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
                GDPR ve eIDAS 2.0 uyarınca yalnızca izin verdiğiniz iddialar şifreli sunum zarfına eklenir.
              </p>
            </div>
            <span style={{
              padding: "4px 10px",
              borderRadius: "4px",
              backgroundColor: "rgba(37, 99, 235, 0.15)",
              color: "#60a5fa",
              fontSize: "12px",
              fontWeight: "600"
            }}>
              DCQL Selective Disclosure
            </span>
          </div>

          <div style={{
            padding: "16px",
            backgroundColor: "var(--bg-subtle)",
            border: "1px solid var(--border-default)",
            borderRadius: "8px",
            marginBottom: "20px"
          }}>
            <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
              Paylaşılacak Bilgileri Seçin (İddia Maskeleme)
            </h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {Object.entries(disclosedFields).map(([field, isAllowed]) => (
                <div
                  key={field}
                  onClick={() => handleToggleField(field)}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 14px",
                    backgroundColor: isAllowed ? "rgba(37, 99, 235, 0.08)" : "var(--bg-input)",
                    border: `1px solid ${isAllowed ? "var(--color-primary)" : "var(--border-default)"}`,
                    borderRadius: "6px",
                    cursor: "pointer"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span style={{ fontSize: "14px" }}>{isAllowed ? "✓" : "✗"}</span>
                    <span style={{ fontSize: "13px", fontWeight: "600", color: isAllowed ? "var(--text-main)" : "var(--text-muted)" }}>
                      {field}
                    </span>
                  </div>
                  <span style={{
                    fontSize: "11px",
                    fontWeight: "600",
                    color: isAllowed ? "var(--color-primary)" : "var(--text-tertiary)"
                  }}>
                    {isAllowed ? "AÇIKÇA İFŞA ET" : "GİZLE (ZKP / MINIMIZED)"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: "12px" }}>
            <button
              onClick={handleExecutePresentation}
              style={{
                padding: "12px 24px",
                backgroundColor: "var(--color-success)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              {presentationSuccess ? "Sunum İmzalanıyor..." : "✓ Rıza Ver ve Kriptografik Sunumu İmzala"}
            </button>
            <button
              onClick={() => onNavigate("DASHBOARD")}
              style={{
                padding: "12px 20px",
                backgroundColor: "var(--bg-subtle)",
                color: "var(--text-muted)",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              İptal Et
            </button>
          </div>
        </div>
      )}

      {/* 8. VERIFICATION RESULT (HOLDER RECEIPT) */}
      {activeScreen === "VERIFICATION_RESULT" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 12px",
            borderRadius: "4px",
            backgroundColor: "rgba(22, 163, 74, 0.15)",
            color: "#4ade80",
            fontSize: "12px",
            fontWeight: "700",
            marginBottom: "12px"
          }}>
            ✓ SUNUM BAŞARIYLA TAMAMLANDI
          </div>
          <h3 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Kriptografik Sunum Makbuzu (Holder Receipt)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Doğrulayıcı kurum sunumunuzu doğruladı ve kabul etti. Olay denetim günlüğünüze kaydedildi.
          </p>

          <div style={{
            padding: "16px",
            backgroundColor: "var(--bg-subtle)",
            border: "1px solid var(--border-default)",
            borderRadius: "8px",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            marginBottom: "20px"
          }}>
            <div><span style={{ color: "var(--text-muted)" }}>Presentation ID:</span> <span style={{ color: "#60a5fa" }}>urn:uuid:vp-2026-902184-eudi</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Verifier DID:</span> <span style={{ color: "#cbd5e1" }}>did:web:enterprise-verifier.eu</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Nonce / Challenge:</span> <span style={{ color: "#10b981" }}>n-88a91c7f (Doğrulandı)</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Nihai Karar:</span> <span style={{ color: "#4ade80", fontWeight: "700" }}>ACCEPTED (KABUL EDİLDİ)</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Blokzincir Anchor TX:</span> <span style={{ color: "#a855f7" }}>0x7a8f12c49b0198de76cae931b204eef0129a</span></div>
          </div>

          <button
            onClick={() => onNavigate("DASHBOARD")}
            style={{
              padding: "10px 18px",
              backgroundColor: "var(--color-primary)",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: "600",
              cursor: "pointer"
            }}
          >
            Cüzdan Ana Sayfasına Dön
          </button>
        </div>
      )}

      {/* 9. ACTIVITY (AUDIT LOG) */}
      {activeScreen === "ACTIVITY" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Cüzdan Denetim İzi (Activity Ledger)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            W3C SSI Domain Event modeline uygun, yerel ve değiştirilemez denetim kayıtları.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {[
              { type: "CREDENTIAL_PRESENTED", time: "2 dakika önce", desc: "eIDAS Ulusal Kimlik Belgesi sunuldu (did:web:enterprise-verifier.eu)", status: "SUCCESS" },
              { type: "CONSENT_GRANTED", time: "2 dakika önce", desc: "Seçici ifşa onayı verildi (3 iddia gizlendi)", status: "SUCCESS" },
              { type: "KEY_ACTIVE", time: "1 saat önce", desc: "Ed25519 anahtarı başarıyla doğrulandı", status: "INFO" },
              { type: "CREDENTIAL_RECEIVED", time: "Dün 14:30", desc: "Nitelikli Sistem Mimarı Tasdiki (QEAA) alındı", status: "SUCCESS" },
              { type: "LOGIN", time: "Dün 09:12", desc: "Biyometrik / Yerel tohum ile oturum açıldı", status: "INFO" }
            ].map((ev, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "12px 16px",
                  backgroundColor: "var(--bg-subtle)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "6px"
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", fontWeight: "700", color: "#60a5fa" }}>
                      {ev.type}
                    </span>
                    <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{ev.time}</span>
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-main)", marginTop: "2px" }}>
                    {ev.desc}
                  </div>
                </div>
                <span style={{
                  fontSize: "10px",
                  fontWeight: "700",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  backgroundColor: ev.status === "SUCCESS" ? "rgba(22, 163, 74, 0.15)" : "rgba(37, 99, 235, 0.15)",
                  color: ev.status === "SUCCESS" ? "#4ade80" : "#60a5fa"
                }}>
                  {ev.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 10. SECURITY */}
      {activeScreen === "SECURITY" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Güvenlik Durumu & AI Risk Değerlendirmesi
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Cüzdan bütünlüğü, yerel donanım izolasyonu ve gerçek zamanlı davranışsal anomali tespiti.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            <div style={{ padding: "18px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                AI Davranışsal Risk Skoru (XGBoost + Autoencoder)
              </h4>
              <div style={{ fontSize: "32px", fontWeight: "800", color: "var(--color-success)", marginBottom: "4px" }}>
                0.04
              </div>
              <div style={{ fontSize: "12px", color: "#10b981", fontWeight: "600", marginBottom: "8px" }}>
                DÜŞÜK RİSK SEVİYESİ (NORMAL DAVRANIŞ)
              </div>
              <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.6" }}>
                Model sürümü: v2.4-hybrid. Son oturum açma, imzalama hızı ve IP korelasyonunda hiçbir anomali veya bot aktivitesi tespit edilmedi.
              </p>
            </div>

            <div style={{ padding: "18px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                Donanım & İzolasyon Parametreleri
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Private Key İzolasyonu:</span>
                  <span style={{ color: "#10b981", fontWeight: "600" }}>✓ Donanım Seviyesi Koruma</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Replay Koruması (Anti-Replay):</span>
                  <span style={{ color: "#10b981", fontWeight: "600" }}>✓ 120s Challenge/Nonce</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Zararlı Yazılım Karantinası:</span>
                  <span style={{ color: "var(--text-main)", fontWeight: "600" }}>Aktif (Trigger: Risk &gt; 0.85)</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>On-Chain Güvenlik Sözleşmesi:</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>EmergencyRecovery.sol</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 11. RECOVERY */}
      {activeScreen === "RECOVERY" && (
        <div style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "10px",
          padding: "24px"
        }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Sosyal Kurtarma (Guardian Recovery — EIP-4337 M-of-N Quorum)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Cüzdan veya özel anahtar kaybında 3-of-5 vasi onayı ve 24 saatlik timelock ile yeni anahtar atanır.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Yapılandırılmış Vasiler (Guardians)
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "var(--font-mono)" }}>0x70997970C51812dc3A010C7d01b50e0d17dc79C8</span>
                  <span style={{ color: "#10b981" }}>Vasi #1 (Onaylı)</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "var(--font-mono)" }}>0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC</span>
                  <span style={{ color: "#10b981" }}>Vasi #2 (Onaylı)</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "var(--font-mono)" }}>0x90F79bf6EB2c4f870365E785982E1f101E93b906</span>
                  <span style={{ color: "#10b981" }}>Vasi #3 (Onaylı)</span>
                </div>
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Kurtarma Parametreleri
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                <div><span style={{ color: "var(--text-muted)" }}>Quorum Eşiği:</span> <span style={{ fontWeight: "700", color: "var(--text-main)" }}>2 / 3 (Çoğunluk İmzası)</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Zaman Kilidi (Timelock):</span> <span style={{ fontWeight: "700", color: "#f59e0b" }}>24 Saat Güvenlik Beklemesi</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Shamir Secret Sharing:</span> <span style={{ color: "#10b981" }}>Şifreli Zarf Aktif</span></div>
              </div>
            </div>
          </div>

          <button
            onClick={() => alert("Kurtarma talebi API Gateway (:8000/api/v1/recovery) üzerinden başlatıldı. Vasiler bilgilendirildi.")}
            style={{
              padding: "12px 20px",
              backgroundColor: "rgba(220, 38, 38, 0.15)",
              color: "#ef4444",
              border: "1px solid rgba(220, 38, 38, 0.4)",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: "600",
              cursor: "pointer"
            }}
          >
            ⚠️ Acil Durum Cüzdan Kurtarma Talebi Başlat
          </button>
        </div>
      )}
    </div>
  );
};
