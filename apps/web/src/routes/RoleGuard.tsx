import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth, UserProfile } from "../context/AuthContext";

export type AllowedRole = "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN";

interface RoleGuardProps {
  children: React.ReactNode;
  allowedRole?: AllowedRole | AllowedRole[];
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
  requireAuth = true
}) => {
  const { user, isAuthenticated, isDemoEvaluationMode } = useAuth();
  const location = useLocation();

  // If strict auth is required and user is neither authenticated nor in demo mode
  if (requireAuth && !isAuthenticated && !isDemoEvaluationMode) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  // If specific roles are restricted
  if (allowedRole && user) {
    const roles = Array.isArray(allowedRole) ? allowedRole : [allowedRole];
    if (!roles.includes(user.role)) {
      // If user has a different role, redirect to their role home
      const fallbackPath = 
        user.role === "HOLDER" ? "/wallet" :
        user.role === "ISSUER" ? "/issuer" :
        user.role === "VERIFIER" ? "/verifier" :
        user.role === "GUARDIAN" ? "/guardian" : "/admin";

      return <Navigate to={fallbackPath} replace />;
    }
  }

  return <>{children}</>;
};
