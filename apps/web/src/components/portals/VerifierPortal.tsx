import React, { useState } from "react";

export type VerifierScreen = 
  | "DASHBOARD" | "CREATE_REQUEST" | "QR_LINK" | "PRESENTATION" | "VERIFICATION_RESULT" | "HISTORY";

export const VerifierPortal: React.FC<{ activeScreen: VerifierScreen; onNavigate: (screen: VerifierScreen) => void }> = ({
  activeScreen,
  onNavigate
}) => {
  // Query builder state
  const [targetCredential, setTargetCredential] = useState<string>("NationalIdentityCredential");
  const [requestedClaims, setRequestedClaims] = useState<string>("Adı Soyadı, Uyruk, Güven Seviyesi (LoA)");
  const [isPolicyPassed, setIsPolicyPassed] = useState<boolean>(true);
  const [aiRiskScore, setAiRiskScore] = useState<number>(0.04);
  const [simulatedAttack, setSimulatedAttack] = useState<boolean>(false);

  const dcqlQueryObj = {
    credentials: [
      {
        id: "cred_query_1",
        format: "ldp_vc",
        meta: {
          type_values: [targetCredential]
        },
        claims: [
          { id: "claim_subject", path: ["credentialSubject"] }
        ]
      }
    ]
  };
  const qrUri = `openid4vp://authorize?client_id=did:web:enterprise-verifier.eu&response_uri=http://localhost:8000/api/v1/identity/presentations/verify&response_type=vp_token&response_mode=direct_post&nonce=n-88a91c7f&dcql_query=${encodeURIComponent(JSON.stringify(dcqlQueryObj))}`;

  const toggleAttackSimulation = () => {
    if (!simulatedAttack) {
      setSimulatedAttack(true);
      setIsPolicyPassed(false);
      setAiRiskScore(0.89); // High Risk!
    } else {
      setSimulatedAttack(false);
      setIsPolicyPassed(true);
      setAiRiskScore(0.04);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div role="note" style={{ padding: "9px 12px", borderRadius: "7px", backgroundColor: "rgba(245, 158, 11, 0.10)", border: "1px solid rgba(245, 158, 11, 0.3)", color: "#fbbf24", fontSize: "12px" }}>
        DEMO SIMULATION: the embedded portal uses local illustrative state and fixed sample values; its request, verification, and risk controls do not call the backend. Sample issuers are not EUDI/eIDAS trusted entities. Use the dedicated verifier pages for backend workflows.
      </div>
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
                Doğrulayıcı Portalı (Relying Party / Verifier — OID4VP 1.0)
              </div>
              <h2 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>
                Kriptografik Sunum ve Güven Doğrulama Merkezi
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
                Verifier DID: <span style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>did:web:enterprise-verifier.eu</span>
              </p>
            </div>
            <button
              onClick={() => onNavigate("CREATE_REQUEST")}
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
              📝 Yeni Sunum Talebi Oluştur (DCQL)
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Demo Sayaçları</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "var(--text-main)", marginTop: "6px" }}>1,428 (sample)</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Gerçek kullanım metriği değildir</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Verification Latency</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#60a5fa", marginTop: "6px" }}>Not measured</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>No performance claim</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Synthetic Risk Scenario</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#f59e0b", marginTop: "6px" }}>Sample only</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>No live threat count or quarantine is shown</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "8px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Sorgu Protokolü</div>
              <div style={{ fontSize: "24px", fontWeight: "800", color: "#a855f7", marginTop: "6px" }}>OID4VP 1.0</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Full signed credential profile</div>
            </div>
          </div>

          <div style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-default)",
            borderRadius: "10px",
            padding: "20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)" }}>
                Sentetik Sunum Sonucunu Görüntüleyin
              </h4>
              <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                Ayrı kontrol ayrıntısı dönmeyen endpoint'e gönderilen demo sunumun aggregate backend sonucu.
              </p>
            </div>
            <button
              onClick={() => onNavigate("VERIFICATION_RESULT")}
              style={{
                padding: "8px 16px",
                backgroundColor: "var(--bg-subtle)",
                color: "var(--text-main)",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Matrisi Görüntüle →
            </button>
          </div>
        </div>
      )}

      {/* 2. CREATE REQUEST */}
      {activeScreen === "CREATE_REQUEST" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            OID4VP 1.0 & DCQL Sunum Talebi Oluşturucu
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Cüzdan sahibinden talep edilecek kimlik türü ve seçici ifşa parametrelerini belirleyin.
          </p>

          <div style={{ maxWidth: "600px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                Talep Edilen Belge Türü
              </label>
              <select
                value={targetCredential}
                onChange={(e) => setTargetCredential(e.target.value)}
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
                <option value="NationalIdentityCredential">Synthetic National Identity Example</option>
                <option value="QualifiedElectronicAttestationCredential">Nitelikli Sistem Mimarı Tasdiki (QEAA)</option>
                <option value="FinancialComplianceCredential">Kurumsal Bankacılık AML / KYC Tasdiki</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                İstenen İddialar (DCQL sorgusu; claim-level cryptographic disclosure desteklenmez)
              </label>
              <input
                type="text"
                value={requestedClaims}
                onChange={(e) => setRequestedClaims(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-main)",
                  fontSize: "13px"
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                Tazelik Nonce & Challenge
              </label>
              <input
                type="text"
                readOnly
                value="n-88a91c7f990218ab (Server-generated, 120s TTL)"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-input)",
                  border: "1px solid var(--border-default)",
                  color: "#10b981",
                  fontFamily: "var(--font-mono)",
                  fontSize: "12px"
                }}
              />
            </div>

            <button
              onClick={() => onNavigate("QR_LINK")}
              style={{
                marginTop: "10px",
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
              📲 Talep QR Kodu & Derin Bağlantı Üret →
            </button>
          </div>
        </div>
      )}

      {/* 3. QR / REQUEST LINK */}
      {activeScreen === "QR_LINK" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            OID4VP 1.0 Canlı Doğrulama QR Kodu
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Holder cüzdanı bu karekodu okuyarak veya aşağıdaki derin bağlantıyı kullanarak sunumu iletir.
          </p>

          <div style={{ display: "flex", gap: "32px", alignItems: "flex-start" }}>
            {/* Visual QR Code simulation container */}
            <div style={{
              padding: "20px",
              backgroundColor: "#ffffff",
              borderRadius: "12px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.3)"
            }}>
              <div style={{
                width: "180px",
                height: "180px",
                backgroundColor: "#000000",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                fontFamily: "var(--font-mono)",
                fontSize: "11px",
                textAlign: "center",
                padding: "10px",
                backgroundImage: "radial-gradient(#ffffff 20%, transparent 20%)",
                backgroundSize: "10px 10px"
              }}>
                <span style={{ backgroundColor: "#000000", padding: "6px", borderRadius: "4px" }}>
                  OID4VP 1.0<br/>QR SCANNER
                </span>
              </div>
              <span style={{ fontSize: "11px", color: "#64748b", marginTop: "8px", fontWeight: "600" }}>
                OID4VP 1.0 / DCQL Uyumlu
              </span>
            </div>

            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "4px" }}>
                  OID4VP Derin Bağlantı (Deep Link)
                </label>
                <textarea
                  readOnly
                  value={qrUri}
                  rows={4}
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "6px",
                    backgroundColor: "var(--bg-input)",
                    border: "1px solid var(--border-default)",
                    fontFamily: "var(--font-mono)",
                    fontSize: "11px",
                    color: "#93c5fd"
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  onClick={() => onNavigate("PRESENTATION")}
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
                  📥 Gelen Sunumu İncele (Presentation) →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. PRESENTATION PAYLOAD */}
      {activeScreen === "PRESENTATION" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)" }}>
                Gelen Verifiable Presentation (VP) JSON-LD Zarfı
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
                Holder tarafından imzalanmış, challenge ve domain bağlı sunum kanıtı.
              </p>
            </div>
            <button
              onClick={() => onNavigate("VERIFICATION_RESULT")}
              style={{
                padding: "8px 16px",
                backgroundColor: "var(--color-success)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              ✅ Kriptografik & AI Doğrulamayı Başlat →
            </button>
          </div>

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
  "type": ["VerifiablePresentation"],
  "verifiableCredential": [
    {
      "id": "urn:uuid:synthetic-identity-demo-001",
      "type": ["VerifiableCredential", "NationalIdentityCredential"],
      "issuer": "did:web:issuer.example",
      "credentialSubject": {
        "id": "did:key:example-holder",
        "Example name": "Synthetic Demo Holder",
        "Example nationality": "Not a real identity",
        "Assurance level": "Not assessed (synthetic example)"
      }
    }
  ],
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": "did:key:example-holder#key-1",
    "challenge": "demo-nonce",
    "domain": "verifier.example",
    "proofValue": "DEMO-ONLY-NOT-A-VALID-SIGNATURE"
  }
}, null, 2)}
          </pre>
        </div>
      )}

      {/* 5. VERIFICATION RESULT (SECTION 13 VERBATIM SPECIFICATION) */}
      {activeScreen === "VERIFICATION_RESULT" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <div>
              <h3 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-main)" }}>
                Doğrulama Sonucu & Karar Matrisi
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
                Master Plan Bölüm 13'te belirtilen resmî 9 kontrol ve nihai policy engine kararı.
              </p>
            </div>

            <button
              onClick={toggleAttackSimulation}
              style={{
                padding: "6px 14px",
                backgroundColor: simulatedAttack ? "rgba(220, 38, 38, 0.15)" : "var(--bg-subtle)",
                color: simulatedAttack ? "#ef4444" : "var(--text-muted)",
                border: `1px solid ${simulatedAttack ? "rgba(220, 38, 38, 0.4)" : "var(--border-default)"}`,
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              {simulatedAttack ? "⚠️ Saldırı/Anomali Modu Aktif" : "⚡ Saldırı Simülasyonu Yap"}
            </button>
          </div>

          {/* Section 13 Verbatim Specification Box */}
          <div style={{
            maxWidth: "520px",
            backgroundColor: "#070a12",
            border: `2px solid ${isPolicyPassed ? "var(--color-success)" : "var(--color-danger)"}`,
            borderRadius: "8px",
            padding: "24px",
            fontFamily: "var(--font-mono)",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5)"
          }}>
            <div style={{
              fontSize: "15px",
              fontWeight: "800",
              letterSpacing: "0.08em",
              color: "#ffffff",
              paddingBottom: "10px",
              borderBottom: "1px solid #1f2937",
              marginBottom: "16px"
            }}>
              VERIFICATION RESULT
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "13px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Credential</span>
                <span style={{ color: "#4ade80", fontWeight: "700" }}>✓ Valid</span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Issuer / Trust</span>
                <span style={{ color: "#4ade80", fontWeight: "700" }}>✓ Valid</span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Signature</span>
                <span style={{ color: isPolicyPassed ? "#4ade80" : "#ef4444", fontWeight: "700" }}>
                  {isPolicyPassed ? "✓ Valid" : "✗ Invalid"}
                </span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Holder Binding</span>
                <span style={{ color: "#4ade80", fontWeight: "700" }}>✓ Valid</span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Expiration</span>
                <span style={{ color: "#4ade80", fontWeight: "700" }}>✓ Valid</span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Revocation / Status</span>
                <span style={{ color: "#4ade80", fontWeight: "700" }}>✓ Clear</span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Challenge</span>
                <span style={{ color: "#4ade80", fontWeight: "700" }}>✓ Valid</span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: "#94a3b8" }}>AI Risk</span>
                <span style={{
                  color: isPolicyPassed ? "#4ade80" : "#ef4444",
                  fontWeight: "700",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  backgroundColor: isPolicyPassed ? "rgba(22, 163, 74, 0.15)" : "rgba(220, 38, 38, 0.15)"
                }}>
                  {isPolicyPassed ? `LOW (${aiRiskScore})` : `HIGH (${aiRiskScore})`}
                </span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Blockchain Anchor</span>
                <span style={{ color: "#4ade80", fontWeight: "700" }}>✓</span>
              </div>

              <div style={{
                marginTop: "14px",
                paddingTop: "12px",
                borderTop: "1px dashed #1f2937",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center"
              }}>
                <span style={{ color: "#ffffff", fontWeight: "700" }}>FINAL POLICY RESULT</span>
                <span style={{
                  fontSize: "14px",
                  fontWeight: "900",
                  color: isPolicyPassed ? "#4ade80" : "#ef4444",
                  letterSpacing: "0.05em"
                }}>
                  {isPolicyPassed ? "ACCEPTED" : "REJECTED"}
                </span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: "20px", fontSize: "12px", color: "var(--text-muted)", maxWidth: "520px" }}>
            * [DEMO LAB / SYNTHETIC] Portal senaryoları sabit örnek değerler kullanır. Risk heuristiği issuer trust veya credential proof'u kanıtlamaz.
          </div>
        </div>
      )}

      {/* 6. HISTORY */}
      {activeScreen === "HISTORY" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Doğrulama Denetim Günlüğü (History)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Geçmiş sunum oturumları, kriptografik kontroller ve politika sonuçları.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-default)", textAlign: "left", color: "var(--text-muted)" }}>
                <th style={{ padding: "10px" }}>Oturum ID</th>
                <th style={{ padding: "10px" }}>Holder DID</th>
                <th style={{ padding: "10px" }}>Belge Türü</th>
                <th style={{ padding: "10px" }}>AI Risk</th>
                <th style={{ padding: "10px" }}>Zaman</th>
                <th style={{ padding: "10px", textAlign: "right" }}>Nihai Sonuç</th>
              </tr>
            </thead>
            <tbody>
              {[
                { id: "demo-session-001", did: "did:key:example-holder", type: "SyntheticCredentialExample", risk: "sample", time: "Sample", res: "DEMO" },
                { id: "demo-session-002", did: "did:key:example-holder", type: "SyntheticQualificationExample", risk: "sample", time: "Sample", res: "DEMO" },
                { id: "sess-7719b", did: "did:key:z6MkuAnom...", type: "NationalIdentityCredential", risk: "HIGH (0.92)", time: "1 saat önce", res: "REJECTED" }
              ].map(item => (
                <tr key={item.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{item.id}</td>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{item.did}</td>
                  <td style={{ padding: "10px", color: "var(--text-main)" }}>{item.type}</td>
                  <td style={{ padding: "10px", color: item.risk.startsWith("LOW") ? "#10b981" : "#ef4444" }}>{item.risk}</td>
                  <td style={{ padding: "10px", color: "var(--text-tertiary)" }}>{item.time}</td>
                  <td style={{ padding: "10px", textAlign: "right" }}>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: "rgba(148, 163, 184, 0.12)",
                      color: "var(--text-muted)"
                    }}>
                      {item.res}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
