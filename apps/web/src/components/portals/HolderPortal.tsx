import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { useWallet } from "../../context/WalletContext";
import { fetchCredentials, type CredentialStatus } from "../../services/api";

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
  status: CredentialStatus;
  claims: Record<string, unknown>;
  proofValue: string;
  statusListIndex?: number;
  aiRiskScore: number;
  policyRule: {
    description: string;
    predicate: string;
    hiddenFields: string[];
  };
}

const INITIAL_FALLBACK_CREDENTIALS: VerifiableCredentialItem[] = [
  {
    id: "urn:uuid:demo-identity-0001",
    title: "Synthetic Demo Identity Credential",
    category: "IDENTITY",
    type: "NationalIdentityCredential",
    issuer: "did:web:issuer.example",
    issuerName: "Demo Issuer (not independently trusted)",
    issuedDate: "2025-01-15",
    expiryDate: "2035-01-15",
    status: "UNKNOWN",
    claims: {
      "Example name": "Synthetic Demo Holder",
      "Example identifier": "DEMO-0001",
      "Example nationality": "Not a real identity",
      "Example date": "2000-01-01",
      "Example location": "Example City",
      "Assurance level": "Not assessed",
      "Example serial": "SAMPLE-01"
    },
    proofValue: "DEMO-ONLY-NOT-A-VALID-SIGNATURE",
    aiRiskScore: 4,
    policyRule: {
      description: "Illustrative rule only",
      predicate: "No credential verification is performed for this fallback sample",
      hiddenFields: []
    }
  },
  {
    id: "urn:uuid:demo-qualification-0002",
    title: "Synthetic Demo Qualification Credential",
    category: "QUALIFIED",
    type: "QualifiedElectronicAttestationCredential",
    issuer: "did:web:issuer.example",
    issuerName: "Demo Issuer (not independently trusted)",
    issuedDate: "2025-06-20",
    expiryDate: "2028-06-20",
    status: "UNKNOWN",
    claims: {
      "Example subject": "Synthetic Demo Holder",
      "Example title": "Prototype systems engineer",
      "Example scope": "Local SSI demonstration",
      "Example reference": "DEMO-QEAA-0002",
      "Example standard": "Not assessed"
    },
    proofValue: "DEMO-ONLY-NOT-A-VALID-SIGNATURE",
    aiRiskScore: 6,
    policyRule: {
      description: "Illustrative rule only",
      predicate: "No credential verification is performed for this fallback sample",
      hiddenFields: []
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

  // Fetch real credentials from backend on load
  useEffect(() => {
    fetchCredentials()
      .then((backendCreds) => {
        if (backendCreds && backendCreds.length > 0) {
          const mapped: VerifiableCredentialItem[] = backendCreds.map((c) => ({
            id: c.id,
            title: c.title,
            category: (c.category as VerifiableCredentialItem["category"]) || "IDENTITY",
            type: c.credential_type,
            issuer: c.issuer,
            issuerName: c.issuer_name || "Issuer not provided by service",
            issuedDate: c.issued_date,
            expiryDate: c.expiry_date || "Süresiz",
            status: c.status,
            statusListIndex: c.status_list_index,
            claims: typeof c.claims === "string" ? JSON.parse(c.claims) : (c.claims || {}),
            proofValue: c.proof_value || "Proof not provided by service",
            aiRiskScore: c.ai_risk_score ?? 0,
            policyRule: {
              description: `${c.title} DCQL Minimizasyon Kuralı`,
              predicate: c.zkp_predicate || "No cryptographic validity claim is provided by this metadata",
              hiddenFields: []
            }
          }));
          setCredentials(mapped);
          setSelectedCredential(mapped[0]);
        }
      });
  }, []);
  
  // Present & Consent state
  const [requestUri, setRequestUri] = useState("openid4vp://authorize?client_id=did:web:verifier.example&response_uri=http://localhost:8000/api/v1/identity/presentations/verify&nonce=demo-nonce&dcql_query=demo-query");
  const [disclosedFields, setDisclosedFields] = useState<Record<string, boolean>>({
    "Example name": true,
    "Assurance level": true,
    "Example identifier": false,
    "Example serial": false,
    "Example date": false,
    "Example location": false,
    "Example nationality": true
  });
  const [presentationSuccess, setPresentationSuccess] = useState<boolean>(false);
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
    setKeyRotatedMsg("Bu gömülü demo yalnızca ekrandaki durumu simüle eder; gerçek anahtar veya DID değiştirilmedi.");
    setTimeout(() => setKeyRotatedMsg(null), 5000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <aside role="note" style={{ padding: "12px 16px", border: "1px solid rgba(245, 158, 11, 0.45)", borderRadius: "8px", backgroundColor: "rgba(245, 158, 11, 0.1)", color: "#fbbf24", fontSize: "0.82rem" }}>
        DEMO SIMULATION: this embedded portal uses synthetic credential values, not official identity data or a trusted issuer. Its presentation, consent, key-rotation, and recovery controls do not submit a signed presentation or change a backend key. The connected wallet pages provide server-backed workflows.
      </aside>
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
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Synthetic credential fixtures · not validated</div>
            </div>

            <div style={{
              padding: "16px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "8px"
            }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Güven Seviyesi (LoA)</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#10b981", marginTop: "6px" }}>Not assessed</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>No independent assurance assessment</div>
            </div>

            <div style={{
              padding: "16px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "8px"
            }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>AI Davranışsal Risk Puanı</div>
              <div style={{ fontSize: "17px", fontWeight: "800", color: "#38bdf8", marginTop: "6px" }}>Değerlendirme yok</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>[DEMO LAB / SYNTHETIC] Canlı skor değil</div>
            </div>

            <div style={{
              padding: "16px",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "8px"
            }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Demo Recovery Display</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#a855f7", marginTop: "6px" }}>Illustrative</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>No live quorum state or chain transaction</div>
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
            Synthetic DID document example
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            This embedded portal renders a local example only; it does not create, resolve, or publish a DID document.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>Example DID method</div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)" }}>did:example (reserved sample method)</div>
              <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>No key or proof is generated in this embedded portal.</div>
            </div>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>Demo wallet address</div>
              <div style={{ fontSize: "13px", fontFamily: "var(--font-mono)", color: "#10b981" }}>{user?.walletAddress || account || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"}</div>
              <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>Illustrative value; no deployed contract or EIP-4337 account is implied.</div>
            </div>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
              Illustrative JSON-LD only — not a published DID document
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
  "id": user?.did || "did:example:holder-001",
  "verificationMethod": [
    {
      "id": `${user?.did || "did:example:holder-001"}#key-1`,
      "type": "Ed25519VerificationKey2020",
      "controller": user?.did || "did:example:holder-001",
      "publicKeyMultibase": "z6MkExampleDemoPublicKeyMultibase"
    }
  ],
  "authentication": [
    `${user?.did || "did:example:holder-001"}#key-1`
  ],
  "assertionMethod": [
    `${user?.did || "did:example:holder-001"}#key-1`
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

              {/* Key recovery is not implemented in this embedded prototype portal. */}
              <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
                <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "4px" }}>
                  Cüzdan kurtarma bu prototipte kullanılabilir değil
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "12px" }}>
                  Bu ekran anahtar dışa aktaramaz veya geri yükleyemez. Gerçek bir kurtarma ifadesini buraya girmeyin.
                </p>
              </div>
            </div>

            {/* Key Policy rules */}
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "10px" }}>
                Güvenlik Prensipleri (Master Plan)
              </h4>
              <ul style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.7", paddingLeft: "16px" }}>
                <li>This embedded portal creates no signing key and exports no wallet secret.</li>
                <li>Key rotation and DID document updates are not implemented by these demo controls.</li>
                <li>Risk examples shown here do not change credential status.</li>
                <li>Use the connected service pages to inspect backend-reported state.</li>
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
                    <span style={{ fontSize: "10px", color: vc.status === "ACTIVE" ? "var(--color-success)" : "#fbbf24", fontWeight: "600" }}>
                      {vc.status === "ACTIVE" ? "✓ " : ""}{vc.status}
                    </span>
                  </div>
                  <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginBottom: "6px" }}>
                    {vc.title}
                  </h4>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "12px" }}>
                    İhraççı: {vc.issuerName}
                  </div>
                  <div style={{ fontSize: "11px", color: "#64748b" }}>
                    Status-list index: #{vc.statusListIndex ?? "Not provided"}
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
                  <span style={{ color: "var(--text-muted)" }}>Status-list index:</span>
                  <div style={{ fontFamily: "var(--font-mono)", color: "var(--text-main)", marginTop: "2px" }}>
                    {selectedCredential.statusListIndex ?? "Not provided"}; status not evaluated in this view
                  </div>
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
    "id": user?.did || "did:example:holder-001",
    ...selectedCredential.claims
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
                <div><span style={{ color: "var(--text-muted)" }}>Relying Party:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>did:web:verifier.example (sample)</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Response URI:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#cbd5e1" }}>/api/v1/identity/presentations/verify</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Demo Challenge / Nonce:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#10b981" }}>demo-nonce (not validated)</span></div>
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

      {/* 7. LEGACY CONSENT SCREEN (DEMO SIMULATION) */}
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
                Bu örnek paneldeki anahtarlar yalnızca yerel önizlemeyi değiştirir. Tam imzalı credential paylaşılır; claim-level cryptographic selective disclosure desteklenmez.
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
              Demo DCQL match · full-credential profile
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
              Demo Alan Görünümü (Aktarılan Credential'ı Değiştirmez)
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
                    {isAllowed ? "ÖNİZLEMEDE GÖSTER" : "ÖNİZLEMEDE GİZLE"}
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
              {presentationSuccess ? "Demo akışı simüle ediliyor…" : "Demo sunum akışını simüle et"}
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
            DEMO SIMULATION · Backend sonucu değildir
          </div>
          <h3 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Örnek Sunum Özeti (Demo Only)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Bu yerel akış sunumu doğrulamaz, backend'e göndermez veya denetim olayı oluşturmaz.
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
            <div><span style={{ color: "var(--text-muted)" }}>Presentation ID:</span> <span style={{ color: "#60a5fa" }}>No backend presentation created</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Verifier:</span> <span style={{ color: "#cbd5e1" }}>Synthetic example</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Nonce / Challenge:</span> <span style={{ color: "#10b981" }}>Not validated</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Nihai Karar:</span> <span style={{ color: "var(--text-muted)", fontWeight: "700" }}>No backend result</span></div>
            <div><span style={{ color: "var(--text-muted)" }}>Blockchain Anchor TX:</span> <span style={{ color: "var(--text-muted)" }}>None reported</span></div>
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
            Demo Activity Examples
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Aşağıdakiler statik örnek satırlardır; gerçek kullanıcı etkinliği veya değiştirilemez kayıt değildir.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {[
              { type: "DEMO_CREDENTIAL_PRESENTED", time: "Sample", desc: "Synthetic example; no verifier request was sent", status: "DEMO" },
              { type: "DEMO_CONSENT_PREVIEW", time: "Sample", desc: "Preview toggles do not change transmitted credential claims", status: "DEMO" },
              { type: "DEMO_KEY_STATE", time: "Sample", desc: "No device key or backend key rotation is proven", status: "DEMO" },
              { type: "DEMO_CREDENTIAL_RECEIVED", time: "Sample", desc: "Illustrative credential only", status: "DEMO" },
              { type: "DEMO_LOGIN", time: "Sample", desc: "No biometric or local-seed login is implemented by this screen", status: "DEMO" }
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
                Risk Heuristiği (sentetik demo)
              </h4>
              <div style={{ fontSize: "32px", fontWeight: "800", color: "var(--color-success)", marginBottom: "4px" }}>
                Değerlendirme yok
              </div>
              <div style={{ fontSize: "12px", color: "#10b981", fontWeight: "600", marginBottom: "8px" }}>
                Canlı skor üretilmedi
              </div>
              <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.6" }}>
                Eğitilmiş model yoktur. Sentetik prototip sinyalleri dışında oturum veya cihaz gözlemi yapılmamıştır.
              </p>
            </div>

            <div style={{ padding: "18px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                Donanım & İzolasyon Parametreleri
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Private Key İzolasyonu:</span>
                  <span style={{ color: "var(--text-muted)", fontWeight: "600" }}>Not available in this embedded demo</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Replay Koruması (Anti-Replay):</span>
                  <span style={{ color: "var(--text-muted)", fontWeight: "600" }}>Backend session required; not measured here</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Zararlı Yazılım Karantinası:</span>
                  <span style={{ color: "var(--text-muted)", fontWeight: "600" }}>No malware quarantine status is queried here</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>Blockchain state:</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>No deployed contract is assumed</span>
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
            Sosyal Kurtarma Akışı (UI demo; no live recovery state)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Bu örnek görünüm Guardian onayı, timelock, DID imzası veya anahtar rotasyonu doğrulamaz. Gerçek durum Recovery Service ekranından alınmalıdır.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Yapılandırılmış Vasiler (Guardians)
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "var(--font-mono)" }}>guardian-1.example</span>
                  <span style={{ color: "var(--text-muted)" }}>Sample only · not approved</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "var(--font-mono)" }}>guardian-2.example</span>
                  <span style={{ color: "var(--text-muted)" }}>Sample only · not approved</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "var(--font-mono)" }}>guardian-3.example</span>
                  <span style={{ color: "var(--text-muted)" }}>Sample only · not approved</span>
                </div>
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Kurtarma Parametreleri
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                <div><span style={{ color: "var(--text-muted)" }}>Demo Eşik Değeri:</span> <span style={{ fontWeight: "700", color: "var(--text-main)" }}>2 / 3 (UI sample)</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Timelock:</span> <span style={{ fontWeight: "700", color: "var(--text-muted)" }}>Not verified in this screen</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Shamir backend workflow:</span> <span style={{ color: "var(--text-muted)" }}>This screen does not verify its state</span></div>
              </div>
            </div>
          </div>

          <button
            onClick={() => alert("Demo only: no recovery request was sent and no guardian was notified.")}
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
            ⚠️ Demo Kurtarma Akışını Simüle Et (İstek Gönderilmez)
          </button>
        </div>
      )}
    </div>
  );
};
