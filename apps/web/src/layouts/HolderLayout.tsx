import React from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { IdentityPermission } from "../context/AuthContext";
import { Wallet, QrCode, Clock, Shield } from "lucide-react";
import { BrandMark } from "../components/common/BrandMark";

/**
 * HolderLayout — deliberate responsive layout for the Holder Wallet experience.
 *
 * Breakpoints:
 *   Mobile  < 768 px  → single column, max-width 480 px, bottom nav dock
 *   Tablet  768–1023  → centred, max-width 768 px, bottom nav dock
 *   Desktop ≥ 1024    → wide content area, max-width 1140 px, top nav bar
 *
 * The old hardcoded `maxWidth: "540px"` caused the wallet to appear as a
 * narrow phone strip on 1920 × 1080 displays. This file removes that
 * constraint and delivers three intentionally-designed viewport experiences.
 */

const NAV_ITEMS: Array<{
  path: string;
  label: string;
  icon: typeof Wallet;
  permission?: IdentityPermission;
}> = [
  { path: "/wallet",          label: "Wallet",   icon: Wallet, permission: "wallets:read" },
  { path: "/wallet/scan",     label: "Scan QR",  icon: QrCode, permission: "wallets:read" },
  { path: "/wallet/activity", label: "Activity", icon: Clock, permission: "presentations:read" },
  { path: "/wallet/security", label: "Security", icon: Shield, permission: "wallet:key:read" },
];

/* ---- inline style helpers ---- */

const styles = {
  /* outer shell — full height, dark background */
  shell: {
    flex: 1,
    display: "flex",
    flexDirection: "column" as const,
    backgroundColor: "var(--bg-app)",
    minHeight: "100vh",
  },

  /* Desktop top navigation bar (≥ 1024 px). Hidden on mobile / tablet via CSS
     class "holder-desktop-nav" which is controlled by the injected <style>. */
  desktopNav: {
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 32px",
    height: "60px",
    backgroundColor: "var(--bg-surface)",
    borderBottom: "1px solid var(--border-default)",
    position: "sticky" as const,
    top: 0,
    zIndex: 60,
  },

  desktopNavBrand: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    fontWeight: 700,
    fontSize: "0.95rem",
    color: "var(--text-main)",
    letterSpacing: "-0.01em",
  },

  desktopNavLinks: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
  },

  /* main content area — scrollable */
  content: {
    flex: 1,
    width: "100%",
    margin: "0 auto",
    padding: "24px 16px 80px",
  },

  /* Wallet holder identity header card */
  holderCard: {
    backgroundColor: "var(--bg-surface)",
    borderRadius: "16px",
    border: "1px solid var(--border-default)",
    padding: "16px 20px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    boxShadow: "0 4px 16px rgba(0,0,0,0.35)",
    marginBottom: "20px",
  },

  avatar: {
    width: "44px",
    height: "44px",
    borderRadius: "50%",
    background: "linear-gradient(135deg, #2563eb, #1d4ed8)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#ffffff",
    fontWeight: 700,
    fontSize: "1.1rem",
    flexShrink: 0,
  },

  /* Bottom navigation dock (mobile + tablet) */
  bottomDock: {
    position: "fixed" as const,
    bottom: 0,
    left: 0,
    right: 0,
    height: "62px",
    backgroundColor: "var(--bg-surface)",
    borderTop: "1px solid var(--border-default)",
    justifyContent: "space-around",
    alignItems: "center",
    zIndex: 50,
    boxShadow: "0 -4px 20px rgba(0,0,0,0.5)",
  },
};

export const HolderLayout: React.FC = () => {
  const { user } = useAuth();
  const location = useLocation();
  const visibleNavItems = NAV_ITEMS.filter(
    (item) => !item.permission || user?.permissions.includes(item.permission)
  );

  const isActive = (path: string) => {
    if (path === "/wallet") {
      return location.pathname === "/wallet"
        || location.pathname.startsWith("/wallet/credentials/")
        || location.pathname === "/wallet/consent"
        || location.pathname === "/consent/presentation";
    }
    return location.pathname === path;
  };

  /* Shared nav link renderer for both desktop and mobile */
  const NavLink: React.FC<{ item: typeof NAV_ITEMS[number]; vertical?: boolean }> = ({
    item,
    vertical = false,
  }) => {
    const Icon = item.icon;
    const active = isActive(item.path);
    return (
      <Link
        key={item.path}
        to={item.path}
        aria-current={active ? "page" : undefined}
        style={{
          display: "flex",
          flexDirection: vertical ? "column" : "row",
          alignItems: "center",
          gap: vertical ? "2px" : "6px",
          textDecoration: "none",
          color: active ? "var(--color-primary)" : "var(--text-muted)",
          fontSize: vertical ? "0.72rem" : "0.85rem",
          fontWeight: active ? 700 : 500,
          padding: vertical ? "6px 14px" : "6px 12px",
          borderRadius: "8px",
          transition: "all 0.15s ease",
          background: active && !vertical ? "rgba(37,99,235,0.12)" : "transparent",
        }}
      >
        <Icon size={vertical ? 20 : 16} strokeWidth={active ? 2.5 : 2} />
        <span>{item.label}</span>
      </Link>
    );
  };

  return (
    <>
      {/*
        Responsive breakpoint rules injected as a <style> tag so we can keep
        the component in pure inline-style / TSX without importing a CSS file.
      */}
      <style>{`
        .holder-desktop-nav  { display: none; }
        .holder-bottom-dock  { display: flex; }
        .holder-content-area { max-width: 480px; }

        @media (min-width: 768px) {
          .holder-content-area { max-width: 768px; }
        }

        @media (min-width: 1024px) {
          .holder-desktop-nav  { display: flex; }
          .holder-bottom-dock  { display: none;  }
          .holder-content-area { max-width: 1140px; padding-bottom: 40px; }
        }
      `}</style>

      <div className="holder-layout-shell" style={styles.shell}>
        {/* ── Desktop top nav bar ── */}
        <nav className="holder-desktop-nav" style={styles.desktopNav} aria-label="Holder workspace navigation">
          <div style={styles.desktopNavBrand}>
            <span className="app-brand-mark holder-brand-mark"><BrandMark size={27} /></span>
            <span>Credential wallet</span>
          </div>
          <div style={styles.desktopNavLinks}>
            {visibleNavItems.map((item) => (
              <NavLink key={item.path} item={item} vertical={false} />
            ))}
          </div>
        </nav>

        {/* ── Main content ── */}
        <div
          className="holder-content-area"
          style={{ ...styles.content, margin: "0 auto", width: "100%" }}
        >
          {/* Holder identity header card */}
          <div style={styles.holderCard}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div style={styles.avatar}>
                {user?.name ? user.name[0].toUpperCase() : "H"}
              </div>
              <div>
                <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
                  {user?.name || "Holder account"}
                </div>
                <div
                  style={{
                    fontSize: "0.78rem",
                    color: "var(--text-muted)",
                  }}
                >
                  {user?.email || "Credential wallet"}
                </div>
              </div>
            </div>
          </div>

          {/* Nested page content */}
          <Outlet />
        </div>

        {/* ── Mobile / tablet bottom navigation dock ── */}
        <nav className="holder-bottom-dock" style={styles.bottomDock} aria-label="Holder workspace navigation">
          {visibleNavItems.map((item) => (
            <NavLink key={item.path} item={item} vertical />
          ))}
        </nav>
      </div>
    </>
  );
};
