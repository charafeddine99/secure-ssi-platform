import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";

export type IssuerScreen = 
  | "DASHBOARD" | "TEMPLATES" | "ISSUE" | "ISSUED" | "REVOCATION" | "ORGANIZATION";

interface CredentialTemplate {
  id: string;
  name: string;
  type: string;
  category: string;
  schemaVersion: string;
  defaultClaims: Record<string, string>;
}

const TEMPLATES: CredentialTemplate[] = [
  {
    id: "tmpl-natid-v2",
    name: "eIDAS Ulusal Dijital Kimlik Belgesi (High LoA)",
    type: "NationalIdentityCredential",
    category: "IDENTITY",
    schemaVersion: "W3C VC 2.0 / eIDAS Annex I",
    defaultClaims: {
      "Adı Soyadı": "Charaf Eddine Bessanane",
      "Ulusal Kimlik No": "TR-10293847561",
      "Uyruk": "T.C. & AB Uygunluk",
      "Doğum Tarihi": "1999-04-12",
      "Doğum Yeri": "İstanbul",
      "Güven Seviyesi (LoA)": "eIDAS High (Qualified)"
    }
  },
  {
    id: "tmpl-qeaa-v2",
    name: "Nitelikli Sistem Mimarı Nitelik Tasdiki (QEAA)",
    type: "QualifiedElectronicAttestationCredential",
    category: "QUALIFIED",
    schemaVersion: "W3C VC 2.0 / eIDAS Annex V",
    defaultClaims: {
      "Sertifika Sahibi": "Charaf Eddine Bessanane",
      "Unvan": "Senior Distributed Systems Architect",
      "Yetki Kapsamı": "W3C VC 2.0 / OID4VCI / OID4VP Cryptographic Engine",
      "Akreditasyon No": "EU-QEAA-9981-SEC"
    }
  },
  {
    id: "tmpl-aml-kyc-v2",
    name: "Kurumsal Bankacılık AML / KYC Tasdiki",
    type: "FinancialComplianceCredential",
    category: "FINANCE",
    schemaVersion: "W3C VC 2.0 / FATF Compliant",
    defaultClaims: {
      "Müşteri Kimliği": "DID-HOLDER-902184",
      "KYC Seviyesi": "Tier 3 (Enhanced Due Diligence)",
      "AML Risk Profili": "Low Risk / Compliant",
      "FATF Raporlama": "Verified Clean"
    }
  }
];

interface IssuedItem {
  id: string;
  recipientDid: string;
  templateName: string;
  issuedAt: string;
  status: "ACTIVE" | "REVOKED";
  statusListIndex: number;
  txHash: string;
}

const INITIAL_ISSUED: IssuedItem[] = [
  {
    id: "urn:uuid:eudi-natid-2026-tr-9021",
    recipientDid: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
    templateName: "eIDAS Ulusal Dijital Kimlik Belgesi (High LoA)",
    issuedAt: "2026-01-15 11:20",
    status: "ACTIVE",
    statusListIndex: 104,
    txHash: "0x892a...102b"
  },
  {
    id: "urn:uuid:qeaa-arch-2026-cert-4401",
    recipientDid: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
    templateName: "Nitelikli Sistem Mimarı Nitelik Tasdiki (QEAA)",
    issuedAt: "2026-02-01 15:40",
    status: "ACTIVE",
    statusListIndex: 288,
    txHash: "0x7a8f...991c"
  },
  {
    id: "urn:uuid:fin-kyc-aml-tier3-8812",
    recipientDid: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
    templateName: "Kurumsal Bankacılık AML / KYC Tasdiki",
    issuedAt: "2026-02-10 09:15",
    status: "ACTIVE",
    statusListIndex: 512,
    txHash: "0x331e...447a"
  }
];

export const IssuerPortal: React.FC<{ activeScreen: IssuerScreen; onNavigate: (screen: IssuerScreen) => void }> = ({
  activeScreen,
  onNavigate
}) => {
  const { user } = useAuth();

  const [issuedList, setIssuedList] = useState<IssuedItem[]>(INITIAL_ISSUED);
  const [selectedTemplate, setSelectedTemplate] = useState<CredentialTemplate>(TEMPLATES[0]);
  
  // Issue wizard state
  const [recipientDid, setRecipientDid] = useState<string>(user?.did || "did:key:z6MkuBesnaSecureHolder2026Ed25519");
  const [formClaims, setFormClaims] = useState<Record<string, string>>(TEMPLATES[0].defaultClaims);
  const [isIssuing, setIsIssuing] = useState(false);
  const [issueResult, setIssueResult] = useState<{
    offerUri: string;
    credentialId: string;
    statusListIndex: number;
    txHash: string;
  } | null>(null);

  const handleSelectTemplate = (tmpl: CredentialTemplate) => {
    setSelectedTemplate(tmpl);
    setFormClaims(tmpl.defaultClaims);
    setIssueResult(null);
  };

  const handleClaimChange = (key: string, value: string) => {
    setFormClaims(prev => ({ ...prev, [key]: value }));
  };

  const handleExecuteIssuance = () => {
    setIsIssuing(true);
    setTimeout(() => {
      const newId = `urn:uuid:${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      const newIndex = Math.floor(Math.random() * 1000) + 600;
      const fakeTx = `0x${Math.random().toString(16).substring(2, 10)}...${Math.random().toString(16).substring(2, 6)}`;
      const offer = `openid-credential-offer://?credential_issuer=http://localhost:8000/api/v1/identity&credential_definition={"type":["${selectedTemplate.type}"]}&grants={"urn:ietf:params:oauth:grant-type:pre-authorized_code":{"pre-authorized_code":"pac_${Date.now()}"}}`;

      const newItem: IssuedItem = {
        id: newId,
        recipientDid,
        templateName: selectedTemplate.name,
        issuedAt: new Date().toISOString().replace("T", " ").substring(0, 16),
        status: "ACTIVE",
        statusListIndex: newIndex,
        txHash: fakeTx
      };

      setIssuedList(prev => [newItem, ...prev]);
      setIssueResult({
        offerUri: offer,
        credentialId: newId,
        statusListIndex: newIndex,
        txHash: fakeTx
      });
      setIsIssuing(false);
    }, 1200);
  };

  const handleRevoke = (id: string) => {
    setIssuedList(prev => prev.map(item => {
      if (item.id === id) {
        return { ...item, status: "REVOKED" };
      }
      return item;
    }));
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
                Güvenilir İhraççı Portalı (Credential Issuer — OID4VCI 1.0)
              </div>
              <h2 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>
                Yetkili Kimlik ve Belge İhraç Merkezi
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
                Issuer DID: <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>did:web:trust.eudi.europa.eu</span>
              </p>
            </div>
            <button
              onClick={() => onNavigate("ISSUE")}
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
              ✍️ Yeni Belge İhraç Et (OID4VCI)
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Toplam İhraç Edilen</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "var(--text-main)", marginTop: "6px" }}>{issuedList.length} Belge</div>
              <div style={{ fontSize: "11px", color: "var(--color-success)", marginTop: "4px" }}>✓ W3C VC 2.0 Standart</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Aktif İhraç Şablonu</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#60a5fa", marginTop: "6px" }}>{TEMPLATES.length} Adet</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>eIDAS Qualified Schemas</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>İptal Listesi Durumu</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#10b981", marginTop: "6px" }}>Bitstring 2021</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>RevocationRegistry.sol Anchor</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Protokol Desteği</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#a855f7", marginTop: "6px" }}>OID4VCI 1.0</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Pre-Auth & DPoP Entegre</div>
            </div>
          </div>

          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "20px" }}>
            <h3 style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-main)", marginBottom: "16px" }}>
              Son İhraç Edilen Belgeler (Canlı Sicil Kaydı)
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {issuedList.slice(0, 4).map(item => (
                <div
                  key={item.id}
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
                    <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)" }}>{item.templateName}</div>
                    <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "2px" }}>
                      Alıcı: {item.recipientDid}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: item.status === "ACTIVE" ? "rgba(22, 163, 74, 0.15)" : "rgba(220, 38, 38, 0.15)",
                      color: item.status === "ACTIVE" ? "#4ade80" : "#ef4444"
                    }}>
                      {item.status}
                    </span>
                    <div style={{ fontSize: "10px", color: "var(--text-tertiary)", marginTop: "4px" }}>{item.issuedAt}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. TEMPLATES */}
      {activeScreen === "TEMPLATES" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            W3C VC 2.0 İhraç Şablon Kataloğu
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Avrupa Dijital Kimlik Çerçevesi (EUDI) ve eIDAS regülasyonu ile uyumlu resmi veri şemaları.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
            {TEMPLATES.map(tmpl => (
              <div
                key={tmpl.id}
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
                  <span style={{
                    fontSize: "10px",
                    fontWeight: "700",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    backgroundColor: "rgba(37, 99, 235, 0.15)",
                    color: "#60a5fa"
                  }}>
                    {tmpl.category}
                  </span>
                  <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "8px", marginBottom: "4px" }}>
                    {tmpl.name}
                  </h4>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "12px" }}>
                    Standart: {tmpl.schemaVersion}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                    İçerilen İddialar: {Object.keys(tmpl.defaultClaims).join(", ")}
                  </div>
                </div>

                <button
                  onClick={() => { handleSelectTemplate(tmpl); onNavigate("ISSUE"); }}
                  style={{
                    marginTop: "16px",
                    padding: "8px 12px",
                    backgroundColor: "var(--color-primary)",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: "600",
                    cursor: "pointer"
                  }}
                >
                  Bu Şablon ile İhraç Et →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. ISSUE CREDENTIAL WIZARD */}
      {activeScreen === "ISSUE" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            OID4VCI 1.0 Standart İhraç Sihirbazı
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            W3C Verifiable Credentials Data Model 2.0 ve Data Integrity Ed25519Signature2020 ile imzalanır.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "24px" }}>
            <div>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                  1. İhraç Şablonu Seçin
                </label>
                <select
                  value={selectedTemplate.id}
                  onChange={(e) => {
                    const found = TEMPLATES.find(t => t.id === e.target.value);
                    if (found) handleSelectTemplate(found);
                  }}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    backgroundColor: "var(--bg-input)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-main)",
                    fontSize: "13px"
                  }}
                >
                  {TEMPLATES.map(t => (
                    <option key={t.id} value={t.id}>{t.name} ({t.category})</option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                  2. Alıcı Holder DID (Cüzdan Adresi)
                </label>
                <input
                  type="text"
                  value={recipientDid}
                  onChange={(e) => setRecipientDid(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    backgroundColor: "var(--bg-input)",
                    border: "1px solid var(--border-default)",
                    color: "#60a5fa",
                    fontSize: "12px",
                    fontFamily: "var(--font-mono)"
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                  3. Şema İddialarını Doldurun (Claims)
                </label>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {Object.entries(formClaims).map(([key, val]) => (
                    <div key={key}>
                      <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{key}</span>
                      <input
                        type="text"
                        value={val}
                        onChange={(e) => handleClaimChange(key, e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          borderRadius: "6px",
                          backgroundColor: "var(--bg-input)",
                          border: "1px solid var(--border-default)",
                          color: "var(--text-main)",
                          fontSize: "12px",
                          marginTop: "2px"
                        }}
                      />
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={handleExecuteIssuance}
                disabled={isIssuing}
                style={{
                  padding: "12px 24px",
                  backgroundColor: "var(--color-primary)",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: "600",
                  cursor: isIssuing ? "not-allowed" : "pointer"
                }}
              >
                {isIssuing ? "Kriptografik İmzalanıyor & Blokzincire Anchor Ediliyor..." : "✍️ İmzala ve Belge Teklifi Üret (OID4VCI)"}
              </button>
            </div>

            {/* Result preview */}
            <div style={{ padding: "20px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                OID4VCI Çıktısı & Teklif Detayı
              </h4>

              {issueResult ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{
                    padding: "10px 14px",
                    backgroundColor: "rgba(22, 163, 74, 0.15)",
                    border: "1px solid rgba(22, 163, 74, 0.3)",
                    borderRadius: "6px",
                    color: "#4ade80",
                    fontSize: "12px",
                    fontWeight: "600"
                  }}>
                    ✓ Belge Başarıyla İmzalandı & StatusList2021'e Yazıldı
                  </div>

                  <div style={{ fontSize: "12px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Credential ID:</span>
                    <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", wordBreak: "break-all" }}>{issueResult.credentialId}</div>
                  </div>

                  <div style={{ fontSize: "12px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Bitstring Status Slot:</span>
                    <div style={{ fontFamily: "var(--font-mono)", color: "#10b981" }}>#{issueResult.statusListIndex} (Active)</div>
                  </div>

                  <div style={{ fontSize: "12px" }}>
                    <span style={{ color: "var(--text-muted)" }}>On-Chain Hash Anchor:</span>
                    <div style={{ fontFamily: "var(--font-mono)", color: "#a855f7" }}>{issueResult.txHash}</div>
                  </div>

                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>OID4VCI Credential Offer URI:</span>
                    <textarea
                      readOnly
                      value={issueResult.offerUri}
                      rows={4}
                      style={{
                        width: "100%",
                        padding: "8px",
                        backgroundColor: "var(--bg-input)",
                        border: "1px solid var(--border-default)",
                        borderRadius: "6px",
                        fontFamily: "var(--font-mono)",
                        fontSize: "11px",
                        color: "#93c5fd",
                        marginTop: "4px"
                      }}
                    />
                  </div>
                </div>
              ) : (
                <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.6" }}>
                  Formu doldurup "İmzala" butonuna bastığınızda, W3C Data Integrity standartlarında Ed25519 imzası atılacak, Bitstring Status List tahsisi yapılacak ve alıcı cüzdanın okuyabilmesi için OID4VCI teklif bağlantısı üretilecektir.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 4. ISSUED CREDENTIALS REGISTRY */}
      {activeScreen === "ISSUED" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            İhraç Edilen Belgeler Sicili
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Kurumunuz tarafından üretilmiş tüm Verifiable Credentials kayıtları ve anlık durumları.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-default)", textAlign: "left", color: "var(--text-muted)" }}>
                <th style={{ padding: "10px" }}>Belge Türü</th>
                <th style={{ padding: "10px" }}>Alıcı DID</th>
                <th style={{ padding: "10px" }}>İhraç Tarihi</th>
                <th style={{ padding: "10px" }}>StatusList Slot</th>
                <th style={{ padding: "10px" }}>Durum</th>
                <th style={{ padding: "10px", textAlign: "right" }}>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {issuedList.map(item => (
                <tr key={item.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <td style={{ padding: "10px", fontWeight: "600", color: "var(--text-main)" }}>{item.templateName}</td>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{item.recipientDid.slice(0, 20)}...</td>
                  <td style={{ padding: "10px", color: "var(--text-muted)" }}>{item.issuedAt}</td>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "#10b981" }}>#{item.statusListIndex}</td>
                  <td style={{ padding: "10px" }}>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: item.status === "ACTIVE" ? "rgba(22, 163, 74, 0.15)" : "rgba(220, 38, 38, 0.15)",
                      color: item.status === "ACTIVE" ? "#4ade80" : "#ef4444"
                    }}>
                      {item.status}
                    </span>
                  </td>
                  <td style={{ padding: "10px", textAlign: "right" }}>
                    {item.status === "ACTIVE" ? (
                      <button
                        onClick={() => handleRevoke(item.id)}
                        style={{
                          padding: "4px 10px",
                          backgroundColor: "rgba(220, 38, 38, 0.15)",
                          color: "#ef4444",
                          border: "1px solid rgba(220, 38, 38, 0.4)",
                          borderRadius: "4px",
                          fontSize: "11px",
                          fontWeight: "600",
                          cursor: "pointer"
                        }}
                      >
                        İptal Et (Revoke)
                      </button>
                    ) : (
                      <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>İptal Edildi</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 5. REVOCATION (BITSTRING STATUS LIST) */}
      {activeScreen === "REVOCATION" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            W3C Bitstring Status List 2021 Yönetimi
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Gizliliği koruyan, O(1) maliyetli bit dizisi iptal kontrol mekanizması ve blokzincir kök hash eşitlemesi.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Status List Meta Verisi
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                <div><span style={{ color: "var(--text-muted)" }}>URI:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>/api/v1/identity/status-lists/status-list-2026</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Boyut:</span> <span style={{ fontWeight: "600", color: "var(--text-main)" }}>131,072 Bit (16 KB GZIP)</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Kök Hash (SHA-256):</span> <span style={{ fontFamily: "var(--font-mono)", color: "#10b981" }}>0xa4b190f82...c31e</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>On-Chain Sözleşme:</span> <span style={{ fontFamily: "var(--font-mono)", color: "#a855f7" }}>RevocationRegistry.sol</span></div>
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Hızlı Bit Çevirme (Bit-Flip Revocation)
              </h4>
              <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
                <input
                  type="number"
                  placeholder="İndeks No (örn: 104)"
                  style={{
                    padding: "8px 12px",
                    borderRadius: "6px",
                    backgroundColor: "var(--bg-input)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-main)",
                    fontSize: "12px",
                    flex: 1
                  }}
                />
                <button
                  onClick={() => alert("Bitstring Status List güncellendi ve on-chain kök hash senkronize edildi.")}
                  style={{
                    padding: "8px 16px",
                    backgroundColor: "var(--color-danger)",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: "600",
                    cursor: "pointer"
                  }}
                >
                  Biti Çevir (İptal Et)
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 6. ORGANIZATION */}
      {activeScreen === "ORGANIZATION" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Kurumsal Kimlik & eIDAS Trust Anchor Profili
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Belge imzalama yetkisine sahip kurumun yasal akreditasyon ve açık anahtar verileri.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "600px", fontSize: "13px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Kurum Unvanı:</span>
              <span style={{ fontWeight: "600", color: "var(--text-main)" }}>European Digital Identity Trust Authority</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Issuer DID:</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>did:web:trust.eudi.europa.eu</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Akreditasyon:</span>
              <span style={{ color: "#10b981", fontWeight: "600" }}>eIDAS Qualified Trust Service Provider (QTSP)</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>İmzalama Kripto Paketi:</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-main)" }}>Ed25519 (RFC 8032) / eddsa-jcs-2022</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Blokzincir Registry:</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "#a855f7" }}>DIDRegistry.sol & RevocationRegistry.sol</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
