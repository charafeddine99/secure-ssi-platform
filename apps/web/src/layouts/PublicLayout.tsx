import React from "react";
import { Outlet, Link } from "react-router-dom";
import { TrustBadge } from "../components/common/TrustBadge";
import { Shield, Layers, Cpu, Database, Key } from "lucide-react";

export const PublicLayout: React.FC = () => {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      <div style={{ flex: 1 }}>
        <Outlet />
      </div>

      {/* Public Footer */}
      <footer
        style={{
          borderTop: "1px solid #1f2937",
          backgroundColor: "#070a12",
          padding: "32px 24px",
          color: "#94a3b8",
          fontSize: "0.8rem"
        }}
      >
        <div style={{ maxWidth: "1200px", margin: "0 auto", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "24px" }}>
          <div>
            <div style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.95rem", marginBottom: "8px" }}>
              Secure SSI Platform
            </div>
            <p style={{ margin: 0, lineHeight: 1.6 }}>
              Academic graduation project and open reference implementation for Self-Sovereign Identity. Built to align with W3C VC 2.0, OpenID4VCI, OpenID4VP, and EUDI ARF draft specifications.
            </p>
            <div style={{ marginTop: "10px" }}>
              <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
            </div>
          </div>

          <div>
            <div style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.9rem", marginBottom: "8px" }}>
              Architectural Layers
            </div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "6px" }}>
              <li>Layer 1: Blockchain Trust Layer (Hardhat EVM, OpenZeppelin)</li>
              <li>Layer 2: AI Fraud & Anomaly Engine (XGBoost + Autoencoder)</li>
              <li>Layer 3: SSI Credential & DID Engine (W3C VC 2.0, Ed25519)</li>
              <li>Layer 4: Universal Client Portals (Holder, Issuer, Verifier, Guardian)</li>
            </ul>
          </div>

          <div>
            <div style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.9rem", marginBottom: "8px" }}>
              Explore Role Portals
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              <Link to="/wallet" style={{ color: "#60a5fa", textDecoration: "none" }}>Holder Wallet</Link> •{" "}
              <Link to="/issuer" style={{ color: "#60a5fa", textDecoration: "none" }}>Issuer Portal</Link> •{" "}
              <Link to="/verifier" style={{ color: "#60a5fa", textDecoration: "none" }}>Verifier Portal</Link> •{" "}
              <Link to="/guardian" style={{ color: "#60a5fa", textDecoration: "none" }}>Guardian Recovery</Link> •{" "}
              <Link to="/admin" style={{ color: "#60a5fa", textDecoration: "none" }}>Admin Console</Link>
            </div>
          </div>
        </div>

        <div style={{ maxWidth: "1200px", margin: "24px auto 0 auto", paddingTop: "16px", borderTop: "1px solid #1f2937", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem" }}>
          <span>© 2026 Academic SSI Platform Prototype. Open Research Reference.</span>
          <span>All blockchain transactions executed on local Hardhat EVM Testnet.</span>
        </div>
      </footer>
    </div>
  );
};
