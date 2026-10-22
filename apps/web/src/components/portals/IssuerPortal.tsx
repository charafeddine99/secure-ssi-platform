import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { createOid4vciOffer, revokeCredential, fetchCredentials, type CredentialStatus, type Oid4vciOffer } from "../../services/api";

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
    name: "[SYNTHETIC DEMO] Identity Credential Example",
    type: "NationalIdCredential",
    category: "IDENTITY",
    schemaVersion: "Local profile example; no eIDAS qualification",
    defaultClaims: {
      "Example name": "Synthetic Holder",
      "Example identifier": "SYNTHETIC-0001",
      "Example nationality": "Not a real identity",
      "Example birth date": "2000-01-01",
      "Assurance level": "Not assessed"
    }
  },
  {
    id: "tmpl-qeaa-v2",
    name: "[SYNTHETIC DEMO] Qualification Example",
    type: "QualifiedElectronicAttestationCredential",
    category: "QUALIFIED",
    schemaVersion: "Local profile example; not a qualified attestation",
    defaultClaims: {
      "Example subject": "Synthetic Holder",
      "Example title": "Prototype systems engineer",
      "Example scope": "Local SSI demonstration",
      "Example reference": "DEMO-QEAA-0001"
    }
  },
  {
    id: "tmpl-aml-kyc-v2",
    name: "[SYNTHETIC DEMO] AML/KYC Example",
    type: "BankKycCredential",
    category: "FINANCE",
    schemaVersion: "Local profile example; no compliance assessment",
    defaultClaims: {
      "Example customer": "Synthetic Holder",
      "KYC level": "Not assessed",
      "AML risk profile": "Not evaluated",
      "Compliance result": "Not evaluated"
    }
  }
];

interface IssuedItem {
  id: string;
  recipientDid: string;
  templateName: string;
  issuedAt: string;
  status: CredentialStatus;
  statusListIndex?: number;
}

export const IssuerPortal: React.FC<{ activeScreen: IssuerScreen; onNavigate: (screen: IssuerScreen) => void }> = ({
  activeScreen,
  onNavigate
}) => {
  const { user } = useAuth();

  const [issuedList, setIssuedList] = useState<IssuedItem[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<CredentialTemplate>(TEMPLATES[0]);
  
  // Issue wizard state
  const [recipientDid, setRecipientDid] = useState<string>(user?.did || "");
  const [formClaims, setFormClaims] = useState<Record<string, string>>(TEMPLATES[0].defaultClaims);
  const [isIssuing, setIsIssuing] = useState(false);
  const [issueResult, setIssueResult] = useState<Oid4vciOffer | null>(null);
  const [issueError, setIssueError] = useState<string | null>(null);

  // Load real issued credentials from database
  useEffect(() => {
    fetchCredentials().then((creds) => {
      if (creds && creds.length > 0) {
        setIssuedList(creds.map((c) => ({
          id: c.id,
          recipientDid: c.user_did,
          templateName: c.title,
          issuedAt: c.issued_date,
          status: c.status,
          statusListIndex: c.status_list_index
        })));
      }
    }).catch(() => setIssuedList([]));
  }, []);

  const handleSelectTemplate = (tmpl: CredentialTemplate) => {
    setSelectedTemplate(tmpl);
    setFormClaims(tmpl.defaultClaims);
    setIssueResult(null);
    setIssueError(null);
  };

  const handleClaimChange = (key: string, value: string) => {
    setFormClaims(prev => ({ ...prev, [key]: value }));
  };

  const handleExecuteIssuance = async () => {
    setIsIssuing(true);
    setIssueError(null);
    try {
      const offer = await createOid4vciOffer({
        credentialConfigurationIds: [selectedTemplate.type],
        subjectData: { ...formClaims, holder_did: recipientDid },
        ttlSeconds: 1800
      });
      setIssueResult(offer);
    } catch (error: unknown) {
      setIssueError(error instanceof Error ? error.message : "OID4VCI offer creation failed.");
    } finally {
      setIsIssuing(false);
    }
  };

  const handleRevoke = async (id: string) => {
    const success = await revokeCredential(id);
    if (success) {
      setIssuedList(prev => prev.map(item => {
        if (item.id === id) {
          return { ...item, status: "REVOKED" };
        }
        return item;
      }));
    } else {
      alert("Credential revocation failed; the displayed status was not changed.");
    }
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
                Local prototype issuer portal · synthetic demonstration data
              </div>
              <h2 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>
                Credential offer workspace
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
                Issuer identity is provided by the configured local service.
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
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Synthetic local examples · not accredited</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>İptal Listesi Durumu</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#10b981", marginTop: "6px" }}>Bitstring Status List 1.0</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Status is backend-managed; anchoring is optional</div>
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
                      backgroundColor: item.status === "ACTIVE" ? "rgba(22, 163, 74, 0.15)" : item.status === "REVOKED" ? "rgba(220, 38, 38, 0.15)" : "rgba(245, 158, 11, 0.12)",
                      color: item.status === "ACTIVE" ? "#4ade80" : item.status === "REVOKED" ? "#ef4444" : "#fbbf24"
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
            Bu katalog sentetik proje örnekleri içerir; resmi EUDI/eIDAS şeması veya akreditasyon iddiası yoktur.
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
            Yapılandırılmış ihraç servisi W3C VC 2.0 profilini ve eddsa-jcs-2022 Data Integrity imzasını kullanır.
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
                disabled={isIssuing || !recipientDid.trim()}
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
                {isIssuing ? "OID4VCI offer is being created..." : "Create OID4VCI Credential Offer"}
              </button>
            </div>

            {/* Result preview */}
            <div style={{ padding: "20px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                OID4VCI Çıktısı & Teklif Detayı
              </h4>

              {issueError ? (
                <div role="alert" style={{ color: "#f87171", fontSize: "12px" }}>{issueError}</div>
              ) : issueResult ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{
                    padding: "10px 14px",
                    backgroundColor: "rgba(245, 158, 11, 0.12)",
                    border: "1px solid rgba(245, 158, 11, 0.3)",
                    borderRadius: "6px",
                    color: "#fbbf24",
                    fontSize: "12px",
                    fontWeight: "600"
                  }}>
                    Offer created. No credential has been issued until a holder claims it.
                  </div>

                  <div style={{ fontSize: "12px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Offer ID:</span>
                    <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa", wordBreak: "break-all" }}>{issueResult.offerId}</div>
                  </div>

                  <div style={{ fontSize: "12px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Offer status:</span>
                    <div style={{ fontFamily: "var(--font-mono)", color: "#fbbf24" }}>{issueResult.status}</div>
                  </div>

                  <div style={{ fontSize: "12px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Credential configuration:</span>
                    <div style={{ fontFamily: "var(--font-mono)", color: "#cbd5e1" }}>{issueResult.credentialConfigurationIds.join(", ")}</div>
                  </div>

                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>OID4VCI deep link:</span>
                    <textarea
                      readOnly
                      value={issueResult.deepLinkUri}
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
                  This local prototype creates an OID4VCI offer. A signed credential and status-list entry exist only after the holder claims it successfully.
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
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "#10b981" }}>{item.statusListIndex != null ? `#${item.statusListIndex}` : "—"}</td>
                  <td style={{ padding: "10px" }}>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: item.status === "ACTIVE" ? "rgba(22, 163, 74, 0.15)" : item.status === "REVOKED" ? "rgba(220, 38, 38, 0.15)" : "rgba(245, 158, 11, 0.12)",
                      color: item.status === "ACTIVE" ? "#4ade80" : item.status === "REVOKED" ? "#ef4444" : "#fbbf24"
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
            W3C Bitstring Status List v1.0 Management
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Servis tarafından sunulan Bitstring Status List verisi. Bu gömülü örnek ekran canlı liste veya zincir üstü kök kanıtı sağlamaz.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
                Status List Meta Verisi
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                <div><span style={{ color: "var(--text-muted)" }}>URI:</span> <span style={{ color: "var(--text-muted)" }}>Not loaded in this embedded demo</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Boyut:</span> <span style={{ color: "var(--text-muted)" }}>Not loaded from service</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Kök Hash:</span> <span style={{ color: "var(--text-muted)" }}>Bu örnek görünümde yüklenmiyor</span></div>
                <div><span style={{ color: "var(--text-muted)" }}>Zincir üstü kanıt:</span> <span style={{ color: "var(--text-muted)" }}>Gerçek makbuz olmadan gösterilmez</span></div>
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
                  onClick={() => alert("Demo görünüm: liste değiştirilmedi. Gerçek iptal işlemi için bağlı Status List sayfasını kullanın.")}
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
            Yapılandırılmış Demo İhraççı Profili
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Bu örnek alan yasal akreditasyon veya dışarıdan doğrulanmış trust anchor göstermez.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "600px", fontSize: "13px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Kurum Unvanı:</span>
              <span style={{ fontWeight: "600", color: "var(--text-main)" }}>Configured Demo Issuer</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Issuer DID:</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{user?.did || "did:web:issuer.example"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Akreditasyon:</span>
              <span style={{ color: "var(--text-muted)", fontWeight: "600" }}>Not independently accredited</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>İmzalama Kripto Paketi:</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-main)" }}>Ed25519 (RFC 8032) / eddsa-jcs-2022</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
              <span style={{ color: "var(--text-muted)" }}>Blokzincir Registry:</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>Optional; no deployment assumed</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
