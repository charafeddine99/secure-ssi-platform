import React, { useState, useEffect } from "react";
import { fetchGatewayStatus, fetchBlockchainStatus, GatewayStatus, BlockchainStatus } from "../../services/api";

export const NetworkIndicator: React.FC = () => {
  const [gateway, setGateway] = useState<GatewayStatus | null>(null);
  const [blockchain, setBlockchain] = useState<BlockchainStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const checkHealth = async () => {
      try {
        const [gw, bc] = await Promise.all([
          fetchGatewayStatus().catch(() => null),
          fetchBlockchainStatus().catch(() => null)
        ]);
        if (mounted) {
          setGateway(gw);
          setBlockchain(bc);
          setLoading(false);
        }
      } catch {
        if (mounted) setLoading(false);
      }
    };
    checkHealth();
    const timer = setInterval(checkHealth, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const isGwOnline = gateway?.gateway_status === "ONLINE";
  const isChainOnline = blockchain?.connected === true;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "0.75rem" }}>
      {/* Gateway Indicator */}
      <div
        title={isGwOnline ? "API Gateway (Port 8000) is Online" : "Connecting to API Gateway..."}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "5px",
          color: isGwOnline ? "#34d399" : "#fbbf24",
          backgroundColor: "rgba(15, 23, 42, 0.6)",
          padding: "3px 8px",
          borderRadius: "6px",
          border: "1px solid rgba(255,255,255,0.08)"
        }}
      >
        <span
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            backgroundColor: isGwOnline ? "#10b981" : "#f59e0b",
            boxShadow: isGwOnline ? "0 0 6px rgba(16,185,129,0.8)" : "none"
          }}
        />
        <span style={{ fontWeight: 500 }}>Gateway</span>
      </div>

      {/* Blockchain Indicator */}
      <div
        title={isChainOnline ? `Hardhat EVM (Block #${blockchain?.block_number})` : "Hardhat Node Local Testnet"}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "5px",
          color: isChainOnline ? "#c084fc" : "#94a3b8",
          backgroundColor: "rgba(15, 23, 42, 0.6)",
          padding: "3px 8px",
          borderRadius: "6px",
          border: "1px solid rgba(255,255,255,0.08)"
        }}
      >
        <span
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            backgroundColor: isChainOnline ? "#a855f7" : "#64748b",
            boxShadow: isChainOnline ? "0 0 6px rgba(168,85,247,0.8)" : "none"
          }}
        />
        <span style={{ fontWeight: 500 }}>
          {isChainOnline ? `EVM #${blockchain?.block_number}` : "EVM Testnet"}
        </span>
      </div>
    </div>
  );
};
