import React, { useState, useEffect } from "react";
import { useWallet } from "../../context/WalletContext";
import { fetchGuardians, approveGuardian, BackendGuardian } from "../../services/api";

export type GuardianScreen = 
  | "REQUESTS" | "REQUEST_DETAIL" | "APPROVE_REJECT" | "HISTORY";

interface RecoveryRequestItem {
  id: string;
  targetDid: string;
  walletAddress: string;
  newProposedKey: string;
  aiRiskScore: number;
  aiRiskVerdict: string;
  createdAt: string;
  timelockRemaining: string;
  approvalsCount: number;
  requiredQuorum: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
}

const INITIAL_REQUESTS: RecoveryRequestItem[] = [
  {
    id: "rec-req-9021-alpha",
    targetDid: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
    walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    newProposedKey: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    aiRiskScore: 0.08,
    aiRiskVerdict: "LOW_RISK (Legitimate Hardware Loss)",
    createdAt: "1 saat önce",
    timelockRemaining: "23 saat 14 dakika",
    approvalsCount: 1,
    requiredQuorum: 2,
    status: "PENDING"
  }
];

export const GuardianPortal: React.FC<{ activeScreen: GuardianScreen; onNavigate: (screen: GuardianScreen) => void }> = ({
  activeScreen,
  onNavigate
}) => {
  const { account } = useWallet();

  const [requests, setRequests] = useState<RecoveryRequestItem[]>(INITIAL_REQUESTS);
  const [selectedRequest, setSelectedRequest] = useState<RecoveryRequestItem>(INITIAL_REQUESTS[0]);
  const [signedMsg, setSignedMsg] = useState<string | null>(null);
  const [liveGuardians, setLiveGuardians] = useState<BackendGuardian[]>([]);

  useEffect(() => {
    fetchGuardians().then(list => {
      if (list && list.length > 0) {
        setLiveGuardians(list);
      }
    });
  }, []);

  const handleApprove = async (reqId: string) => {
    const targetWallet = selectedRequest.walletAddress || "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266";
    // Send real on-chain guardian approval
    await approveGuardian(1, targetWallet);

    setRequests(prev => prev.map(r => {
      if (r.id === reqId) {
        return {
          ...r,
          approvalsCount: r.approvalsCount + 1,
          status: "APPROVED"
        };
      }
      return r;
    }));
    setSignedMsg("✓ Vasi imzanız EIP-4337 EmergencyRecovery.sol sözleşmesine gönderildi. 2/3 Quorum eşiği karşılandı!");
  };

  const handleReject = (reqId: string) => {
    setRequests(prev => prev.map(r => {
      if (r.id === reqId) {
        return { ...r, status: "REJECTED" };
      }
      return r;
    }));
    setSignedMsg("⚠️ Talep vasi tarafından güvenlik gerekçesiyle REDDEDİLDİ. Acil durum iptali tetiklendi.");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* 1. RECOVERY REQUESTS */}
      {activeScreen === "REQUESTS" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "20px"
          }}>
            <div>
              <div style={{ fontSize: "12px", color: "#a855f7", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Sosyal Kurtarma Vasisi (Guardian Portal — EIP-4337 M-of-N Quorum)
              </div>
              <h2 style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-main)", marginTop: "4px" }}>
                Bekleyen Cüzdan Kurtarma Talepleri
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
                Vasi Hesabı: <span style={{ fontFamily: "var(--font-mono)", color: "#10b981" }}>{account || "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"}</span>
              </p>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {requests.map(req => (
              <div
                key={req.id}
                style={{
                  padding: "16px",
                  backgroundColor: "var(--bg-subtle)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "8px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center"
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                    <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)" }}>
                      Talep ID: {req.id}
                    </span>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: req.status === "APPROVED" ? "rgba(22, 163, 74, 0.15)" : "rgba(245, 158, 11, 0.15)",
                      color: req.status === "APPROVED" ? "#4ade80" : "#f59e0b"
                    }}>
                      {req.status} ({req.approvalsCount}/{req.requiredQuorum} Onay)
                    </span>
                  </div>
                  <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>
                    Hedef Cüzdan DID: {req.targetDid}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "4px" }}>
                    Kalan Timelock Süresi: <span style={{ color: "#fcd34d" }}>{req.timelockRemaining}</span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    onClick={() => { setSelectedRequest(req); onNavigate("REQUEST_DETAIL"); }}
                    style={{
                      padding: "8px 14px",
                      backgroundColor: "var(--bg-input)",
                      color: "var(--text-main)",
                      border: "1px solid var(--border-default)",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: "600",
                      cursor: "pointer"
                    }}
                  >
                    Detaylar →
                  </button>
                  <button
                    onClick={() => { setSelectedRequest(req); onNavigate("APPROVE_REJECT"); }}
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
                    İncele & İmzala
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. REQUEST DETAIL */}
      {activeScreen === "REQUEST_DETAIL" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <button
                onClick={() => onNavigate("REQUESTS")}
                style={{ fontSize: "12px", color: "#60a5fa", background: "none", border: "none", cursor: "pointer", marginBottom: "4px" }}
              >
                ← Taleplere Geri Dön
              </button>
              <h3 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-main)" }}>
                Kurtarma Talebi Detayı: {selectedRequest.id}
              </h3>
            </div>
            <button
              onClick={() => onNavigate("APPROVE_REJECT")}
              style={{
                padding: "8px 16px",
                backgroundColor: "var(--color-primary)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Onay / Red Ekranına Git →
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                Talep Parametreleri
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                <div><span style={{ color: "var(--text-muted)" }}>Hedef DID:</span> <div style={{ fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{selectedRequest.targetDid}</div></div>
                <div><span style={{ color: "var(--text-muted)" }}>Mevcut On-Chain Adres:</span> <div style={{ fontFamily: "var(--font-mono)", color: "#cbd5e1" }}>{selectedRequest.walletAddress}</div></div>
                <div><span style={{ color: "var(--text-muted)" }}>Önerilen Yeni Adres:</span> <div style={{ fontFamily: "var(--font-mono)", color: "#10b981" }}>{selectedRequest.newProposedKey}</div></div>
                <div><span style={{ color: "var(--text-muted)" }}>Quorum Durumu:</span> <div style={{ fontWeight: "700", color: "#a855f7" }}>{selectedRequest.approvalsCount} / {selectedRequest.requiredQuorum} (EIP-4337)</div></div>
              </div>
            </div>

            <div style={{ padding: "16px", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-default)" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
                AI Fraud Engine Risk Raporu
              </h4>
              <div style={{ fontSize: "28px", fontWeight: "800", color: "#10b981", marginBottom: "4px" }}>
                {selectedRequest.aiRiskScore}
              </div>
              <div style={{ fontSize: "12px", color: "#10b981", fontWeight: "600", marginBottom: "8px" }}>
                {selectedRequest.aiRiskVerdict}
              </div>
              <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: "1.6" }}>
                XGBoost ve Autoencoder modelleri talep kaynağının güvenilir olduğunu, oturum anomalisi veya SIM-swap şüphesi olmadığını onaylamıştır.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. APPROVE / REJECT */}
      {activeScreen === "APPROVE_REJECT" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "18px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Vasi İmzası ile Onayla veya Reddet (M-of-N Quorum)
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            İmzanız akıllı sözleşmeye (EmergencyRecovery.sol) iletilir. Yeterli çoğunluk (2/3) sağlandığında timelock sonunda cüzdan mülkiyeti transfer edilir.
          </p>

          {signedMsg && (
            <div style={{
              padding: "14px 18px",
              backgroundColor: "rgba(22, 163, 74, 0.15)",
              border: "1px solid rgba(22, 163, 74, 0.3)",
              borderRadius: "8px",
              color: "#4ade80",
              fontSize: "13px",
              fontWeight: "600",
              marginBottom: "20px"
            }}>
              {signedMsg}
            </div>
          )}

          <div style={{
            padding: "20px",
            backgroundColor: "var(--bg-subtle)",
            border: "1px solid var(--border-default)",
            borderRadius: "8px",
            marginBottom: "20px",
            maxWidth: "600px"
          }}>
            <h4 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-main)", marginBottom: "12px" }}>
              İmzalanacak Kurtarma Beyanı (Recovery Attestation)
            </h4>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.7", fontFamily: "var(--font-mono)" }}>
              "Ben yetkili vasi olarak, {selectedRequest.targetDid} cüzdanının yeni anahtarının {selectedRequest.newProposedKey} olarak güncellenmesini onaylıyorum. Timelock: 24h."
            </div>
          </div>

          <div style={{ display: "flex", gap: "14px" }}>
            <button
              onClick={() => handleApprove(selectedRequest.id)}
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
              ✍️ Vasi Olarak Onayla (Quorum Ekle)
            </button>

            <button
              onClick={() => handleReject(selectedRequest.id)}
              style={{
                padding: "12px 24px",
                backgroundColor: "var(--color-danger)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              ⛔ Talebi Reddet & Acil İptal Et
            </button>
          </div>
        </div>
      )}

      {/* 4. HISTORY */}
      {activeScreen === "HISTORY" && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-default)", borderRadius: "10px", padding: "24px" }}>
          <h3 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-main)", marginBottom: "8px" }}>
            Vasi Kararları ve Geçmiş Kurtarma İşlemleri
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
            Geçmişte onaylanan veya reddedilen EIP-4337 kurtarma kayıtları.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-default)", textAlign: "left", color: "var(--text-muted)" }}>
                <th style={{ padding: "10px" }}>Talep ID</th>
                <th style={{ padding: "10px" }}>Hedef Cüzdan</th>
                <th style={{ padding: "10px" }}>Quorum</th>
                <th style={{ padding: "10px" }}>Zaman</th>
                <th style={{ padding: "10px", textAlign: "right" }}>Sonuç</th>
              </tr>
            </thead>
            <tbody>
              {[
                { id: "rec-req-9021-alpha", target: "0xf39Fd...FffFb92266", quorum: "2/3", time: "Bugün", res: "ONAYLANDI" },
                { id: "rec-req-8812-beta", target: "0x70997...0e0d17dc79", quorum: "3/3", time: "Geçen Ay", res: "TAMAMLANDI" }
              ].map(item => (
                <tr key={item.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "#60a5fa" }}>{item.id}</td>
                  <td style={{ padding: "10px", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{item.target}</td>
                  <td style={{ padding: "10px", color: "#a855f7" }}>{item.quorum}</td>
                  <td style={{ padding: "10px", color: "var(--text-tertiary)" }}>{item.time}</td>
                  <td style={{ padding: "10px", textAlign: "right", color: "#4ade80", fontWeight: "700" }}>{item.res}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
