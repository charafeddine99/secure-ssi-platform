import type { AppRole, IdentityPermission } from "../api/session.ts";

export interface NavItem {
  to: string;
  label: string;
  icon: "wallet" | "inbox" | "shield" | "users" | "clock" | "home" | "file" | "plus" | "rotate" | "search" | "check" | "history" | "database" | "cpu" | "landmark" | "archive" | "lifebuoy";
  permission?: IdentityPermission;
  end?: boolean;
}

/** Navigation is derived from the server-issued role and permissions only. */
export const NAVIGATION: Record<AppRole, NavItem[]> = {
  HOLDER: [
    { to: "/wallet", label: "My wallet", icon: "wallet", permission: "wallets:read", end: true },
    { to: "/wallet/scan", label: "Receive or share", icon: "inbox", permission: "wallets:read" },
    { to: "/wallet/security", label: "Keys & recovery", icon: "lifebuoy", permission: "wallet:key:read" },
    { to: "/wallet/backup", label: "Credential backup", icon: "archive", permission: "wallets:backup" },
    { to: "/guardian", label: "Guardian tasks", icon: "users", end: true },
    { to: "/wallet/activity", label: "Activity", icon: "clock", permission: "presentations:read" },
    { to: "/account/security", label: "Account security", icon: "shield" },
  ],
  ISSUER: [
    { to: "/issuer", label: "Overview", icon: "home", permission: "credentials:sign", end: true },
    { to: "/issuer/templates", label: "Credential types", icon: "file", permission: "credentials:sign" },
    { to: "/issuer/issue", label: "Create offer", icon: "plus", permission: "credentials:sign" },
    { to: "/issuer/revocations", label: "Status & revocation", icon: "rotate", permission: "credentials:revoke" },
    { to: "/account/security", label: "Account security", icon: "shield" },
  ],
  VERIFIER: [
    { to: "/verifier", label: "Overview", icon: "home", permission: "presentations:verify", end: true },
    { to: "/verifier/request", label: "New request", icon: "plus", permission: "presentations:verify" },
    { to: "/verifier/verify", label: "Verify presentation", icon: "check", permission: "presentations:verify" },
    { to: "/verifier/history", label: "History", icon: "history", permission: "presentations:read" },
    { to: "/account/security", label: "Account security", icon: "shield" },
  ],
  ADMIN: [
    { to: "/admin", label: "Platform health", icon: "home", permission: "admin:operations:read", end: true },
    { to: "/admin/users", label: "Users & issuer scope", icon: "users", permission: "admin:users:read" },
    { to: "/admin/trust-registry", label: "Trust registry", icon: "landmark", permission: "admin:operations:read" },
    { to: "/admin/audit", label: "Audit log", icon: "history", permission: "admin:operations:read" },
    { to: "/admin/recovery", label: "Recovery oversight", icon: "lifebuoy", permission: "admin:operations:read" },
    { to: "/admin/backups", label: "Platform backup", icon: "archive", permission: "admin:backup:read" },
    { to: "/admin/contracts", label: "Optional anchoring", icon: "database", permission: "admin:operations:read" },
    { to: "/admin/intelligence", label: "Security intelligence", icon: "shield", permission: "admin:operations:read" },
    { to: "/account/security", label: "Account security", icon: "check" },
  ],
};

export function roleHomePath(role: AppRole): string {
  switch (role) {
    case "HOLDER": return "/wallet";
    case "ISSUER": return "/issuer";
    case "VERIFIER": return "/verifier";
    case "ADMIN": return "/admin";
  }
}
