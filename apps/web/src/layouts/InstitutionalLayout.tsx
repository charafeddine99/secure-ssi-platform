import React, { useState } from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { TrustBadge } from "../components/common/TrustBadge";
import { 
  Building2, 
  Search, 
  Users, 
  Settings, 
  FileText, 
  PlusCircle, 
  RotateCcw, 
  History, 
  Cpu, 
  ShieldAlert, 
  Database,
  Menu,
  X
} from "lucide-react";

interface MenuItem {
  path: string;
  label: string;
  icon: any;
}

export const InstitutionalLayout: React.FC = () => {
  const { user } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Determine current institutional section from pathname
  const isIssuer = location.pathname.startsWith("/issuer");
  const isVerifier = location.pathname.startsWith("/verifier");
  const isGuardian = location.pathname.startsWith("/guardian");
  const isAdmin = location.pathname.startsWith("/admin");

  const getRoleConfig = () => {
    if (isIssuer) {
      return {
        roleTitle: "ISSUER OPERATIONS CONSOLE",
        org: user?.organization || "Accredited SSI Issuance Authority (Prototype)",
        accentColor: "#2563eb",
        items: [
          { path: "/issuer", label: "Dashboard", icon: Building2 },
          { path: "/issuer/templates", label: "Credential Templates", icon: FileText },
          { path: "/issuer/issue", label: "Issue Credential", icon: PlusCircle },
          { path: "/issuer/revocations", label: "Revocation Registry", icon: RotateCcw }
        ]
      };
    }
    if (isVerifier) {
      return {
        roleTitle: "VERIFIER TRUST CONSOLE",
        org: user?.organization || "Digital Verification & Trust Inspection Service",
        accentColor: "#059669",
        items: [
          { path: "/verifier", label: "Dashboard", icon: Search },
          { path: "/verifier/request", label: "Create Request", icon: PlusCircle },
          { path: "/verifier/verify", label: "Verify Presentation", icon: FileText },
          { path: "/verifier/history", label: "Audit History", icon: History }
        ]
      };
    }
    if (isGuardian) {
      return {
        roleTitle: "GUARDIAN RECOVERY NETWORK",
        org: user?.organization || "EIP-4337 Social Recovery Network",
        accentColor: "#d97706",
        items: [
          { path: "/guardian", label: "Dashboard", icon: Users },
          { path: "/guardian/requests", label: "Active Petitions", icon: ShieldAlert },
          { path: "/guardian/approve/1", label: "Sign Recovery", icon: RotateCcw }
        ]
      };
    }
    // Admin default
    return {
      roleTitle: "SYSTEM ADMIN & SECURITY COCKPIT",
      org: "SSI Platform Infrastructure & Security Administration",
      accentColor: "#7c3aed",
      items: [
        { path: "/admin", label: "Cockpit Overview", icon: Settings },
        { path: "/admin/contracts", label: "Smart Contracts", icon: Database },
        { path: "/admin/audit", label: "Audit Explorer", icon: History },
        { path: "/admin/fraud-monitor", label: "AI Threat Stream", icon: Cpu }
      ]
    };
  };

  const config = getRoleConfig();

  return (
    <div style={{ flex: 1, display: "flex", backgroundColor: "#0b0f19" }}>
      {/* Mobile Toggle Button */}
      <div
        style={{
          display: "none",
          position: "fixed",
          bottom: "16px",
          right: "16px",
          zIndex: 60
        }}
        className="mobile-sidebar-toggle"
      >
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          style={{
            padding: "12px",
            borderRadius: "50%",
            backgroundColor: "#2563eb",
            color: "#ffffff",
            border: "none",
            boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
            cursor: "pointer"
          }}
        >
          {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Institutional Left Sidebar */}
      <aside
        style={{
          width: "260px",
          backgroundColor: "#111827",
          borderRight: "1px solid #1f2937",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "20px 16px"
        }}
      >
        <div>
          {/* Section Title */}
          <div style={{ padding: "0 8px 16px 8px", borderBottom: "1px solid #1f2937", marginBottom: "16px" }}>
            <span
              style={{
                fontSize: "0.68rem",
                fontWeight: 800,
                letterSpacing: "0.08em",
                color: config.accentColor,
                textTransform: "uppercase"
              }}
            >
              {config.roleTitle}
            </span>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f8fafc", marginTop: "4px" }}>
              {config.org}
            </div>
            <div style={{ marginTop: "6px" }}>
              <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
            </div>
          </div>

          {/* Navigation Links */}
          <nav style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {config.items.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    fontSize: "0.85rem",
                    fontWeight: isActive ? 700 : 500,
                    textDecoration: "none",
                    color: isActive ? "#ffffff" : "#94a3b8",
                    backgroundColor: isActive ? "rgba(37, 99, 235, 0.15)" : "transparent",
                    border: isActive ? `1px solid rgba(37, 99, 235, 0.3)` : "1px solid transparent",
                    transition: "all 0.15s ease"
                  }}
                >
                  <Icon size={18} color={isActive ? config.accentColor : "#94a3b8"} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer with DID info */}
        <div
          style={{
            padding: "12px",
            backgroundColor: "#0d131f",
            borderRadius: "10px",
            border: "1px solid #1f2937",
            fontSize: "0.72rem"
          }}
        >
          <div style={{ color: "#94a3b8" }}>Active Operator DID:</div>
          <div style={{ color: "#60a5fa", fontFamily: "var(--font-mono)", wordBreak: "break-all", marginTop: "2px" }}>
            {user?.did ? `${user.did.slice(0, 22)}...` : "did:ssi:platform..."}
          </div>
        </div>
      </aside>

      {/* Main Institutional Workspace */}
      <main
        style={{
          flex: 1,
          padding: "28px 32px",
          overflowY: "auto",
          maxWidth: "1400px",
          margin: "0 auto",
          width: "100%"
        }}
      >
        <Outlet />
      </main>
    </div>
  );
};
