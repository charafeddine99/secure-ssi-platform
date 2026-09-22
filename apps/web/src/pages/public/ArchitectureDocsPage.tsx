import React from "react";
import { TrustBadge } from "../../components/common/TrustBadge";
import { Layers, Database, Cpu, Shield, KeyRound, Terminal, ExternalLink } from "lucide-react";

export const ArchitectureDocsPage: React.FC = () => {
  const layers = [
    {
      layer: "Layer 1",
      title: "Blockchain Trust & Anchoring Layer",
      tech: "Hardhat EVM, OpenZeppelin, Solidity 0.8.20",
      description: "Provides tamper-proof decentralized trust anchors, DID registration, and 2-of-3 / 3-of-5 multi-sig social recovery without centralized custodian bottlenecks.",
      contracts: [
        { name: "DIDRegistry.sol", address: "0x5FbDB2315678afecb367f032d93F642f64180aa3", purpose: "Binds user DIDs to initial VC hashes and allows authorized owner rotation." },
        { name: "EmergencyRecovery.sol", address: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512", purpose: "EIP-4337 social recovery with guardian quorum threshold and AI quarantine triggers." },
        { name: "RevocationRegistry.sol", address: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0", purpose: "Anchors W3C Bitstring Status List roots for instant on-chain revocation checks." },
        { name: "AuditLogger.sol", address: "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9", purpose: "Gas-optimized on-chain event log for critical security milestones." }
      ]
    },
    {
      layer: "Layer 2",
      title: "AI Threat & Anomaly Mitigation Engine",
      tech: "Python 3.11, FastAPI (Port 8002), NumPy, Scikit-learn",
      description: "Evaluates issuance and presentation sessions in real-time. Combines gradient boosted decision trees with autoencoder latent reconstruction loss.",
      endpoints: [
        { method: "POST", path: "/api/v1/fraud/assess", desc: "Calculates hybrid risk score (0-100) from 6 behavioral and network features." },
        { method: "GET", path: "/health", desc: "Returns health status of the AI fraud detection microservice." }
      ]
    },
    {
      layer: "Layer 3",
      title: "SSI Credential & DID Engine",
      tech: "Python 3.11, FastAPI (Port 8001), Web3.py, MongoDB Persistence Layer",
      description: "Implements W3C Verifiable Credentials 2.0 issuance with Ed25519 Linked Data signatures, DIDComm v2 encryption, and status list management.",
      endpoints: [
        { method: "POST", path: "/api/issue_credential", desc: "Evaluates AI risk and generates W3C JSON-LD credential signed with Ed25519." },
        { method: "POST", path: "/api/verify_presentation", desc: "Validates Ed25519 signature, status bitstring, and selective disclosure." },
        { method: "GET", path: "/api/user_credentials", desc: "Retrieves active credentials for a given user wallet address." }
      ]
    },
    {
      layer: "Layer 4",
      title: "API Gateway & Universal Client Portals",
      tech: "FastAPI Gateway (Port 8000), React 18, Vite, Ethers.js v6",
      description: "Central reverse-proxy providing unified `/api/v1` routes, CORS handling, system health aggregation, and responsive role-specific portals.",
      endpoints: [
        { method: "GET", path: "/api/v1/system/status", desc: "Aggregated health telemetry for all microservices." },
        { method: "ALL", path: "/api/v1/identity/*", desc: "Reverse-proxy routing to SSI Core (Port 8001)." },
        { method: "ALL", path: "/api/v1/fraud/*", desc: "Reverse-proxy routing to AI Threat Service (Port 8002)." },
        { method: "ALL", path: "/api/v1/recovery/*", desc: "Reverse-proxy routing to Recovery Service (Port 8003)." }
      ]
    }
  ];

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 24px" }}>
      <div style={{ marginBottom: "36px" }}>
        <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "12px" }}>
          <TrustBadge level="STANDARDS_ALIGNED" />
          <TrustBadge level="BLOCKCHAIN_ANCHORED" />
          <TrustBadge level="DEMO_TRUST_LEVEL" />
        </div>
        <h1 style={{ fontSize: "2.2rem", fontWeight: 800, color: "#ffffff", margin: 0 }}>
          4-Layer Architecture & API Specifications
        </h1>
        <p style={{ fontSize: "0.95rem", color: "#94a3b8", marginTop: "6px" }}>
          Comprehensive technical documentation of the graduation thesis SSI system architecture.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
        {layers.map((l) => (
          <div
            key={l.layer}
            style={{
              backgroundColor: "#111827",
              borderRadius: "16px",
              border: "1px solid #1f2937",
              padding: "24px",
              boxShadow: "0 4px 16px rgba(0, 0, 0, 0.4)"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px", marginBottom: "12px" }}>
              <div>
                <span style={{ fontSize: "0.75rem", color: "#60a5fa", fontWeight: 700, textTransform: "uppercase" }}>
                  {l.layer}
                </span>
                <h2 style={{ fontSize: "1.3rem", fontWeight: 700, color: "#ffffff", margin: "2px 0 0 0" }}>
                  {l.title}
                </h2>
              </div>
              <span style={{ fontSize: "0.75rem", backgroundColor: "#161f33", padding: "4px 10px", borderRadius: "6px", color: "#cbd5e1", fontFamily: "var(--font-mono)" }}>
                {l.tech}
              </span>
            </div>

            <p style={{ fontSize: "0.85rem", color: "#94a3b8", lineHeight: 1.6, marginBottom: "20px" }}>
              {l.description}
            </p>

            {/* Smart Contracts List (if Layer 1) */}
            {l.contracts && (
              <div>
                <h4 style={{ fontSize: "0.85rem", color: "#e2e8f0", marginBottom: "10px" }}>
                  Anchored Solidity Smart Contracts (Local Hardhat Node - Port 8545):
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "10px" }}>
                  {l.contracts.map((c) => (
                    <div
                      key={c.name}
                      style={{
                        backgroundColor: "#0d131f",
                        padding: "12px",
                        borderRadius: "8px",
                        border: "1px solid #1f2937"
                      }}
                    >
                      <div style={{ fontWeight: 600, color: "#f8fafc", fontSize: "0.85rem" }}>
                        {c.name}
                      </div>
                      <div style={{ fontSize: "0.7rem", fontFamily: "var(--font-mono)", color: "#c084fc", margin: "4px 0" }}>
                        {c.address}
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                        {c.purpose}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Microservice Endpoints (if Layer 2, 3, 4) */}
            {l.endpoints && (
              <div>
                <h4 style={{ fontSize: "0.85rem", color: "#e2e8f0", marginBottom: "10px" }}>
                  Microservice REST Endpoints:
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {l.endpoints.map((ep) => (
                    <div
                      key={ep.path}
                      style={{
                        backgroundColor: "#0d131f",
                        padding: "10px 14px",
                        borderRadius: "8px",
                        border: "1px solid #1f2937",
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        fontSize: "0.8rem"
                      }}
                    >
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          backgroundColor: ep.method === "POST" ? "rgba(37,99,235,0.2)" : "rgba(16,185,129,0.2)",
                          color: ep.method === "POST" ? "#60a5fa" : "#34d399",
                          fontFamily: "var(--font-mono)"
                        }}
                      >
                        {ep.method}
                      </span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "#f8fafc", fontWeight: 600 }}>
                        {ep.path}
                      </span>
                      <span style={{ color: "#94a3b8", marginLeft: "auto", fontSize: "0.75rem" }}>
                        {ep.desc}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
