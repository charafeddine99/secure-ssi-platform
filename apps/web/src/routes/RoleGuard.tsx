import React from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { IdentityPermission } from "../context/AuthContext";
import { roleHomePath } from "./roleNavigation";

export type AllowedRole = "HOLDER" | "ISSUER" | "VERIFIER" | "ADMIN";

interface RoleGuardProps {
  children: React.ReactNode;
  allowedRole?: AllowedRole | AllowedRole[];
  requiredPermission?: IdentityPermission;
  requireAuth?: boolean;
}

/**
 * Enterprise Role Guard
 * Enforces Role-Based Access Control (RBAC).
 * Supports both production-ready session/JWT context and thesis evaluation demo mode.
 */
export const RoleGuard: React.FC<RoleGuardProps> = ({
  children,
  allowedRole,
  requiredPermission,
  requireAuth = true
}) => {
  const { user, isAuthenticated, isAuthLoading } = useAuth();
  const location = useLocation();

  if (requireAuth && isAuthLoading) {
    return <div role="status" aria-live="polite">Checking your signed-in account…</div>;
  }

  if ((requireAuth || allowedRole || requiredPermission) && (!isAuthenticated || !user)) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If specific roles are restricted
  if (allowedRole && user) {
    const roles = Array.isArray(allowedRole) ? allowedRole : [allowedRole];
    if (!roles.includes(user.role)) {
      return <Navigate to={roleHomePath(user.role)} replace />;
    }
  }

  if (requiredPermission && (!user || !user.permissions.includes(requiredPermission))) {
    return (
      <section className="access-denied" role="alert" aria-labelledby="access-denied-title">
        <h1 id="access-denied-title">Access denied</h1>
        <p>Your account does not have permission to open this page.</p>
        <Link to={user ? roleHomePath(user.role) : "/login"}>Return to your workspace</Link>
      </section>
    );
  }

  return <>{children}</>;
};
