import React, { useEffect, useRef, useState } from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { IdentityPermission } from "../context/AuthContext";
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
  icon: React.ComponentType<{ size?: number; color?: string }>;
  permission?: IdentityPermission;
}

interface RoleConfig {
  roleTitle: string;
  org: string;
  accentColor: string;
  items: MenuItem[];
}

export const InstitutionalLayout: React.FC = () => {
  const { user } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);

  // Determine current institutional section from pathname
  const isIssuer = location.pathname.startsWith("/issuer");
  const isVerifier = location.pathname.startsWith("/verifier");
  const isGuardian = location.pathname.startsWith("/guardian");

  useEffect(() => {
    if (!sidebarOpen) return;
    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => {
      sidebarRef.current?.querySelector<HTMLAnchorElement>("nav a")?.focus();
    });
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSidebarOpen(false);
        menuButtonRef.current?.focus();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        sidebarRef.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)') ?? []
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [sidebarOpen]);

  const getRoleConfig = (): RoleConfig => {
    if (isIssuer) {
      return {
        roleTitle: "Issuer workspace",
        org: "Issuer account",
        accentColor: "#2563eb",
        items: [
          { path: "/issuer", label: "Dashboard", icon: Building2, permission: "credentials:sign" },
          { path: "/issuer/templates", label: "Configurations", icon: FileText, permission: "credentials:sign" },
          { path: "/issuer/issue", label: "Issue Credential", icon: PlusCircle, permission: "credentials:sign" },
          { path: "/issuer/revocations", label: "Revocation Registry", icon: RotateCcw, permission: "credentials:revoke" }
        ]
      };
    }
    if (isVerifier) {
      return {
        roleTitle: "Verifier workspace",
        org: "Verifier account",
        accentColor: "#059669",
        items: [
          { path: "/verifier", label: "Dashboard", icon: Search, permission: "presentations:verify" },
          { path: "/verifier/request", label: "Create Request", icon: PlusCircle, permission: "presentation-challenges:create" },
          { path: "/verifier/verify", label: "Verify Presentation", icon: FileText, permission: "presentations:verify" },
          { path: "/verifier/history", label: "Audit History", icon: History, permission: "presentations:read" }
        ]
      };
    }
    if (isGuardian) {
      return {
        roleTitle: "Recovery workspace",
        org: "Account recovery",
        accentColor: "#d97706",
        items: [
          { path: "/guardian", label: "Dashboard", icon: Users },
          { path: "/guardian/requests", label: "Recovery requests", icon: ShieldAlert }
        ]
      };
    }
    // Admin default
    return {
      roleTitle: "Administration",
      org: "Platform operations",
      accentColor: "#7c3aed",
      items: [
        { path: "/admin", label: "Overview", icon: Settings },
        { path: "/admin/users", label: "Users & institutions", icon: Users, permission: "admin:users:read" },
        { path: "/admin/contracts", label: "Smart Contracts", icon: Database },
        { path: "/admin/audit", label: "Audit Explorer", icon: History },
        { path: "/admin/fraud-monitor", label: "Risk Service", icon: Cpu }
      ]
    };
  };

  const config = getRoleConfig();
  const accountOrganization = user?.organization?.trim();
  const displayOrganization = accountOrganization &&
    accountOrganization !== "Not provided by the Identity Service"
    ? accountOrganization
    : config.org;
  const visibleItems = config.items.filter(
    (item) => !item.permission || user?.permissions.includes(item.permission)
  );
  const workspacePath = isIssuer ? "/issuer" : isVerifier ? "/verifier" : isGuardian ? "/guardian" : "/admin";
  const workspaceName = isIssuer ? "Issuer" : isVerifier ? "Verifier" : isGuardian ? "Recovery" : "Administration";
  const routeNames: Record<string, string> = {
    "/issuer/templates": "Credential configurations",
    "/issuer/issue": "Create credential offer",
    "/issuer/revocations": "Credential status",
    "/verifier/request": "Create verification request",
    "/verifier/verify": "Verify presentation",
    "/verifier/history": "Verification history",
    "/guardian/requests": "Recovery requests",
    "/admin/users": "Users and issuer scope",
    "/admin/contracts": "Contract directory",
    "/admin/audit": "Audit explorer",
    "/admin/fraud-monitor": "Risk service",
  };
  const currentPage = routeNames[location.pathname]
    ?? visibleItems.find((item) => item.path === location.pathname)?.label
    ?? (isGuardian && location.pathname.startsWith("/guardian/approve/") ? "Review recovery request" : workspaceName);
  const isWorkspaceHome = location.pathname === workspacePath;

  return (
    <div className="institutional-shell">
      {sidebarOpen && (
        <button
          type="button"
          className="institutional-sidebar-backdrop"
          aria-label="Close navigation menu"
          onClick={() => {
            setSidebarOpen(false);
            menuButtonRef.current?.focus();
          }}
        />
      )}

      {/* Institutional Left Sidebar */}
      <aside
        ref={sidebarRef}
        id="institutional-navigation"
        className={`institutional-sidebar ${sidebarOpen ? "open" : ""}`}
        aria-label={`${config.roleTitle} workspace`}
      >
        <div>
          {/* Section Title */}
          <div className="institutional-workspace-heading">
            <span>{config.roleTitle}</span>
            <div>{displayOrganization}</div>
          </div>

          {/* Navigation Links */}
          <nav aria-label={`${config.roleTitle} navigation`}>
            {visibleItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => {
                    setSidebarOpen(false);
                    menuButtonRef.current?.focus();
                  }}
                  aria-current={isActive ? "page" : undefined}
                  className="institutional-nav-link"
                >
                  <Icon size={18} aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Signed-in account context */}
        <div
          className="institutional-account-card"
        >
          <div className="institutional-account-label">Signed in as</div>
          <div className="institutional-account-name">
            {user?.name || "Account"}
          </div>
          {user?.email && <div className="institutional-account-email">{user.email}</div>}
        </div>
      </aside>

      {/* Main Institutional Workspace */}
      <main
        className="institutional-main"
      >
        <div className={`institutional-main-toolbar${isWorkspaceHome ? "" : " has-breadcrumb"}`}>
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-label={sidebarOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={sidebarOpen}
            aria-controls="institutional-navigation"
            className="institutional-menu-button"
          >
            {sidebarOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>
          {!isWorkspaceHome && (
            <nav className="institutional-breadcrumb" aria-label="Breadcrumb">
              <Link to={workspacePath}>{workspaceName}</Link>
              <span aria-hidden="true">/</span>
              <span aria-current="page">{currentPage}</span>
            </nav>
          )}
        </div>
        <Outlet />
      </main>
    </div>
  );
};
