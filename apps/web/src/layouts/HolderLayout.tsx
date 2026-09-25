import React from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { TrustBadge } from "../components/common/TrustBadge";
import { Wallet, QrCode, Clock, Shield, KeyRound, ChevronRight } from "lucide-react";

export const HolderLayout: React.FC = () => {
  const { user } = useAuth();
  const location = useLocation();

  const navItems = [
    { path: "/wallet", label: "Wallet", icon: Wallet },
    { path: "/wallet/scan", label: "Scan QR", icon: QrCode },
    { path: "/wallet/activity", label: "Activity", icon: Clock },
    { path: "/wallet/security", label: "Security", icon: Shield }
  ];

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        justifyContent: "center",
        backgroundColor: "#080c16",
        padding: "16px 12px 72px 12px"
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "540px",
          display: "flex",
          flexDirection: "column",
          gap: "16px"
        }}
      >
        {/* Holder Wallet Header Badge */}
        <div
          style={{
            backgroundColor: "#111827",
            borderRadius: "16px",
            border: "1px solid #1f2937",
            padding: "16px 18px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "42px",
                height: "42px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #2563eb, #1d4ed8)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "1.1rem"
              }}
            >
              {user?.name ? user.name[0] : "H"}
            </div>
            <div>
              <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
                {user?.name || "Sovereign Wallet Holder"}
              </div>
              <div style={{ fontSize: "0.72rem", color: "#60a5fa", fontFamily: "var(--font-mono)" }}>
                {user?.did ? `${user.did.slice(0, 16)}...${user.did.slice(-6)}` : "did:key:z6Mku..."}
              </div>
            </div>
          </div>

          <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
        </div>

        {/* Dynamic Nested Page Content */}
        <div style={{ flex: 1 }}>
          <Outlet />
        </div>
      </div>

      {/* Mobile-first Bottom Navigation Dock */}
      <nav
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          height: "60px",
          backgroundColor: "#111827",
          borderTop: "1px solid #1f2937",
          display: "flex",
          justifyContent: "space-around",
          alignItems: "center",
          zIndex: 50,
          maxWidth: "540px",
          margin: "0 auto",
          borderRadius: "16px 16px 0 0",
          boxShadow: "0 -4px 16px rgba(0,0,0,0.5)"
        }}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "2px",
                textDecoration: "none",
                color: isActive ? "#60a5fa" : "#94a3b8",
                fontSize: "0.72rem",
                fontWeight: isActive ? 700 : 500,
                padding: "6px 14px",
                borderRadius: "8px",
                transition: "all 0.15s ease"
              }}
            >
              <Icon size={18} strokeWidth={isActive ? 2.5 : 2} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
};
