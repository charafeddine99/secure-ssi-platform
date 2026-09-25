import React from "react";
import { TrustBadge } from "../../components/common/TrustBadge";
import { Database, ExternalLink, ShieldCheck, CheckCircle2 } from "lucide-react";

export const SmartContractsPage: React.FC = () => {
  const contracts = [
    {
      name: "DIDRegistry.sol",
      address: "0x5FbDB2315678afecb367f032d93F642f64180aa3",
      sourceLines: "135 lines",
      purpose: "Binds user DIDs to initial VC hashes and manages owner-authorized key rotations.",
      methods: ["registerDID(string, bytes32)", "updateVCHash(string, bytes32)", "transferDIDOwnership(string, address)"]
    },
    {
      name: "EmergencyRecovery.sol",
      address: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
      sourceLines: "248 lines",
      purpose: "EIP-4337 social recovery with M-of-N guardian consensus threshold & AI quarantine hooks.",
      methods: ["configureGuardians(address[], uint256)", "initiateRecovery(address, address)", "approveRecovery(address)", "quarantineWallet(address, string)"]
    },
    {
      name: "RevocationRegistry.sol",
      address: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
      sourceLines: "82 lines",
      purpose: "Anchors W3C Bitstring Status List roots for instant verifiable on-chain revocation.",
      methods: ["publishStatusListRoot(bytes32, uint256)", "revokeCredential(bytes32, string)"]
    },
    {
      name: "AuditLogger.sol",
      address: "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
      sourceLines: "42 lines",
      purpose: "Gas-optimized on-chain event log for critical platform security and recovery milestones.",
      methods: ["logSecurityEvent(string, address, uint8)"]
    }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="BLOCKCHAIN_ANCHORED" />
        </div>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          Solidity Smart Contracts Registry
        </h1>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "4px 0 0 0" }}>
          Deployed OpenZeppelin-secured smart contracts running on Ethereum local node (Hardhat Port 8545).
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "20px" }}>
        {contracts.map((c) => (
          <div
            key={c.name}
            style={{
              backgroundColor: "#111827",
              borderRadius: "16px",
              border: "1px solid #1f2937",
              padding: "22px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between"
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#c084fc", fontWeight: 700 }}>
                  {c.sourceLines}
                </span>
                <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(16, 185, 129, 0.1)", color: "#34d399", padding: "2px 8px", borderRadius: "4px", fontWeight: 600 }}>
                  Deployed & Tested (19/19)
                </span>
              </div>

              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#ffffff", margin: "0 0 8px 0" }}>
                {c.name}
              </h3>

              <div style={{ backgroundColor: "#0d131f", padding: "10px 12px", borderRadius: "8px", border: "1px solid #1f2937", marginBottom: "12px" }}>
                <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>EVM Contract Address:</span>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem", color: "#60a5fa", wordBreak: "break-all", marginTop: "2px" }}>
                  {c.address}
                </div>
              </div>

              <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "0 0 16px 0", lineHeight: 1.5 }}>
                {c.purpose}
              </p>

              <div>
                <span style={{ fontSize: "0.72rem", color: "#cbd5e1", fontWeight: 600 }}>
                  Exposed Public Functions:
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "6px" }}>
                  {c.methods.map((m) => (
                    <div
                      key={m}
                      style={{
                        padding: "4px 8px",
                        borderRadius: "4px",
                        backgroundColor: "#0d131f",
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.72rem",
                        color: "#e2e8f0"
                      }}
                    >
                      {m}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ marginTop: "20px", paddingTop: "12px", borderTop: "1px solid #1f2937", fontSize: "0.72rem", color: "#64748b" }}>
              Local Hardhat Node Port 8545 • Chain ID: 31337
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
