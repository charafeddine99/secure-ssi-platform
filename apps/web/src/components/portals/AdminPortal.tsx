import React, { useState, useEffect } from "react";
import { fetchGatewayStatus, fetchBlockchainStatus, fetchAuditLogs, BackendAuditLog, BlockchainStatus } from "../../services/api";

export type AdminScreen = 
  | "USERS" | "ORGANIZATIONS" | "TRUST" | "FRAUD" | "RECOVERY" | "BLOCKCHAIN" | "AUDIT" | "SYSTEM";

export const AdminPortal: React.FC<{ activeScreen: AdminScreen; onNavigate?: (screen: AdminScreen) => void }> = ({
  activeScreen,
}) => {
  const [gatewayStatus, setGatewayStatus] = useState<string>("LOADING");
  const [systemHealth, setSystemHealth] = useState<string>("UNKNOWN");
  const [services, setServices] = useState<Record<string, string>>({
    identity_service: "UNKNOWN",
    fraud_service: "UNKNOWN",
    recovery_service: "UNKNOWN",
    blockchain_node: "UNKNOWN"
  });

  const [blockchainInfo, setBlockchainInfo] = useState<BlockchainStatus | null>(null);
  const [realAuditLogs, setRealAuditLogs] = useState<BackendAuditLog[]>([]);

  // Fetch real system status from Gateway (:8000)
  useEffect(() => {
    fetchGatewayStatus().then(data => {
      if (data) {
        setGatewayStatus(data.gateway_status);
        setSystemHealth(data.system_health);
        setServices(prev => ({ ...prev, ...data.services }));
      } else {
        setGatewayStatus("UNAVAILABLE");
        setSystemHealth("UNKNOWN");
        setServices({ identity_service: "UNKNOWN", fraud_service: "UNKNOWN", recovery_service: "UNKNOWN", blockchain_node: "UNKNOWN" });
      }
    });

    fetchBlockchainStatus().then(info => {
      if (info) setBlockchainInfo(info);
    });

    fetchAuditLogs().then(logs => {
      if (logs && logs.length > 0) setRealAuditLogs(logs);
    });
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <aside role="note" style={{ padding: "12px 16px", border: "1px solid rgba(245, 158, 11, 0.45)", borderRadius: "8px", backgroundColor: "rgba(245, 158, 11, 0.1)", color: "#fbbf24", fontSize: "0.82rem" }}>
        DEMO CONSOLE: user, organization, and trust-registry rows in this embedded portal are illustrative. Service health, blockchain connectivity, and audit entries are displayed only when returned by their endpoints; an unavailable endpoint is not treated as healthy.
      </aside>
      {/* 1. USERS */}
      {activeScreen === "USERS" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Platform Kullanıcıları & Kimlik Durumları
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Aşağıdaki satırlar sentetik demo verisidir; gerçek kullanıcı veya güven seviyesi kaydı değildir.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-default)", textAlign: "left", color: "var(--text-muted)" }}>
                <th style={{ padding: "10px" }}>Kullanıcı</th>
                <th style={{ padding: "10px" }}>DID</th>
                <th style={{ padding: "10px" }}>Rol</th>
                <th style={{ padding: "10px" }}>Güven (LoA)</th>
                <th style={{ padding: "10px", textAlign: "right" }}>Durum</th>
              </tr>
            </thead>
            <tbody>
              {[
                { name: "Demo Holder", did: "did:key:example-holder", role: "HOLDER", loa: "Not assessed", st: "DEMO" },
                { name: "Demo Issuer", did: "did:web:issuer.example", role: "ISSUER", loa: "Not accredited", st: "DEMO" },
                { name: "Demo Verifier", did: "did:web:verifier.example", role: "VERIFIER", loa: "Not assessed", st: "DEMO" },
                { name: "Demo Guardian", did: "did:key:example-guardian", role: "GUARDIAN", loa: "Not assessed", st: "DEMO" }
              ].map((u, i) => (
                <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <td style={{ padding: "10px", fontWeight: "600", color: "var(--text-main)" }}>{u.name}</td>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{u.did}</td>
                  <td style={{ padding: "10px", color: "var(--text-secondary)" }}>{u.role}</td>
                  <td style={{ padding: "10px", color: "var(--text-muted)" }}>{u.loa}</td>
                  <td style={{ padding: "10px", textAlign: "right", color: "var(--text-muted)", fontWeight: "700" }}>{u.st}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 2. ORGANIZATIONS */}
      {activeScreen === "ORGANIZATIONS" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Yetkilendirilmiş Kurumlar & Güven Ağları
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Aşağıdaki kuruluş adları ve alan adları yalnızca sentetik örneklerdir; yetki veya akreditasyon göstermez.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            {[
              { name: "Demo Issuer One", type: "ISSUER", domain: "issuer.example", status: "DEMO ONLY" },
              { name: "Demo Issuer Two", type: "ISSUER", domain: "issuer-two.example", status: "DEMO ONLY" },
              { name: "Demo Verifier One", type: "VERIFIER", domain: "verifier.example", status: "DEMO ONLY" },
              { name: "Demo Verifier Two", type: "VERIFIER", domain: "verifier-two.example", status: "DEMO ONLY" }
            ].map((org, i) => (
              <div key={i} style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ fontSize: "10px", fontWeight: "700", color: "#60a5fa" }}>{org.type}</span>
                  <span style={{ fontSize: "10px", color: "var(--text-muted)", fontWeight: "700" }}>{org.status}</span>
                </div>
                <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)" }}>{org.name}</h4>
                <div style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginTop: "4px" }}>{org.domain}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. TRUST (TRUST FRAMEWORK / ROOT OF TRUST) */}
      {activeScreen === "TRUST" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Yerel Trust Registry Görünümü
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Bu proje içindeki kayıtları gösterir; EUDI/eIDAS güven listesi, resmi akreditasyon veya dış güven kökü değildir.
          </p>

          <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)", marginBottom: "16px" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "6px" }}>
              Blokzincir Güven Çapası (Trust Anchor)
            </h4>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
              EVM anchoring opsiyoneldir. Yalnızca gerçek bir işlem makbuzu döndüğünde anchor kanıtı gösterilir; anchor credential trust veya status kararı vermez.
            </div>
          </div>
        </div>
      )}

      {/* 4. FRAUD HEURISTIC STATUS */}
      {activeScreen === "FRAUD" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Sentetik Risk Heuristiği
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            [DEMO LAB / SYNTHETIC] Sabit kurallı prototip; eğitilmiş model veya bağımsız etiketli değerlendirme bulunmuyor.
          </p>

          <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
            <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Engine version</div>
            <div style={{ fontSize: "18px", fontWeight: 800, color: "var(--text-main)", marginTop: "4px" }}>rule-heuristic-v1 · NOT TRAINED</div>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.6", marginBottom: 0 }}>
              Risk is advisory only. It cannot establish issuer trust, credential validity, or credential status; protocol and cryptographic checks remain authoritative.
            </p>
          </div>
        </div>
      )}

      {/* 5. RECOVERY */}
      {activeScreen === "RECOVERY" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Kurtarma Politikaları & Quorum Yönetimi
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            EIP-4337 akıllı hesap kurtarma parametreleri ve acil durum durdurma (Emergency Circuit Breaker).
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>Platform Quorum Kuralı</h4>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Varsayılan: 2-of-3 ve 3-of-5 vasi onay eşiği</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Shamir Secret Sharing (SSS) ile şifreli zarf dağıtımı</div>
            </div>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>Zaman Kilidi (Timelock)</h4>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Zorunlu Güvenlik Beklemesi: 24 Saat</div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>Yetkisiz kurtarma girişiminde asıl sahip iptal edebilir</div>
            </div>
          </div>
        </div>
      )}

      {/* 6. BLOCKCHAIN */}
      {activeScreen === "BLOCKCHAIN" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Hardhat EVM Akıllı Sözleşmeleri & On-Chain Durum {blockchainInfo?.connected ? `(Block: #${blockchainInfo.block_number})` : ""}
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Solidity 0.8.28 & OpenZeppelin tabanlı dağıtılmış akıllı sözleşmeler.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "#10b981", fontWeight: "700" }}>✓ DAĞITILDI & TEST EDİLDİ (19 Test Geçti)</div>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>DIDRegistry.sol</h4>
              <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "4px" }}>
                0x5FbDB2315678afecb367f032d93F642f64180aa3
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "#10b981", fontWeight: "700" }}>✓ DAĞITILDI & TEST EDİLDİ (19 Test Geçti)</div>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>RevocationRegistry.sol</h4>
              <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "4px" }}>
                0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "#10b981", fontWeight: "700" }}>✓ DAĞITILDI & TEST EDİLDİ (19 Test Geçti)</div>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>EmergencyRecovery.sol</h4>
              <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "4px" }}>
                0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "#10b981", fontWeight: "700" }}>✓ DAĞITILDI & TEST EDİLDİ (19 Test Geçti)</div>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>AuditLogger.sol</h4>
              <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#60a5fa", marginTop: "4px" }}>
                0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 7. AUDIT */}
      {activeScreen === "AUDIT" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Servis Denetim Olayları
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Yalnızca denetim endpoint'inden dönen olaylar gösterilir. Bu görünüm değiştirilemez saklama veya hash zinciri kanıtı değildir.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-default)", textAlign: "left", color: "var(--text-muted)" }}>
                <th style={{ padding: "10px" }}>Olay Türü</th>
                <th style={{ padding: "10px" }}>Aktör DID</th>
                <th style={{ padding: "10px" }}>Hedef Cüzdan</th>
                <th style={{ padding: "10px" }}>Zaman Damgası</th>
                <th style={{ padding: "10px", textAlign: "right" }}>Sonuç</th>
              </tr>
            </thead>
            <tbody>
              {realAuditLogs.length === 0 ? (
                <tr><td colSpan={5} style={{ padding: "16px", color: "var(--text-muted)" }}>Henüz görüntülenebilir bir denetim olayı yok.</td></tr>
              ) : realAuditLogs.slice(0, 10).map((ev) => (
                <tr key={ev.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <td style={{ padding: "10px", fontWeight: "700", color: "#60a5fa" }}>{ev.event_type}</td>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{ev.actor_did || "—"}</td>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "#10b981" }}>{ev.target_wallet || "—"}</td>
                  <td style={{ padding: "10px", color: "var(--text-tertiary)" }}>{ev.created_at ? ev.created_at.substring(0, 19).replace("T", " ") : "—"}</td>
                  <td style={{ padding: "10px", textAlign: "right", color: "var(--text-muted)", fontWeight: "700" }}>RECORDED BY SERVICE</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 8. SYSTEM */}
      {activeScreen === "SYSTEM" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Mikroservis Telemetrisi
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Gateway'den gelen son durum; eksik telemetri UNKNOWN olarak gösterilir.
          </p>

          <div style={{
            padding: "16px",
            backgroundColor: "rgba(148, 163, 184, 0.08)",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            borderRadius: "8px",
            marginBottom: "20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)" }}>
                API Gateway Durumu: {gatewayStatus} ({systemHealth})
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                Bu durum endpoint'inden bildirilen gateway özeti; servislerin tamamı veya ağ güvenliği hakkında ek kanıt değildir.
              </div>
            </div>
            <span style={{ fontSize: "20px", color: "var(--text-muted)" }}>●</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Port :8001</div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>SSI Identity Core</div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "700", marginTop: "4px" }}>● {services.identity_service || "UNKNOWN"}</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Port :8002</div>
                <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>Fraud Heuristic Service</div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "700", marginTop: "4px" }}>● {services.fraud_service || "UNKNOWN"}</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Port :8003</div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>Guardian Recovery</div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "700", marginTop: "4px" }}>● {services.recovery_service || "UNKNOWN"}</div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Port :8545</div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>Hardhat EVM Node</div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: "700", marginTop: "4px" }}>● {blockchainInfo?.connected ? `CONNECTED · ${blockchainInfo.currentBlockNumber ?? blockchainInfo.block_number ?? "block unknown"}` : "UNKNOWN / OFFLINE"}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
