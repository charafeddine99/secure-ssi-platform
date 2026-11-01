import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { IconLock } from "@tabler/icons-react";
import { useAuth } from "../context/AuthContext.ts";
import type { AppRole, IdentityPermission } from "../api/session.ts";
import { roleHomePath } from "./navigation.ts";
import { ButtonLink } from "../components/ui/Button.tsx";
import { LoadingState } from "../components/ui/States.tsx";
import { Alert } from "../components/ui/Alert.tsx";

const Centered: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="page-body">
    <div className="container-tight py-4">{children}</div>
  </div>
);

/**
 * Client-side routing guard. It improves UX only; every API call is still
 * authorised by the backend, which remains the security boundary.
 */
export const RoleGuard: React.FC<{
  children: React.ReactNode;
  allowedRole?: AppRole | AppRole[];
  requiredPermission?: IdentityPermission;
}> = ({ children, allowedRole, requiredPermission }) => {
  const { user, status } = useAuth();
  const location = useLocation();

  if (status === "checking") {
    return <Centered><div className="card"><LoadingState label="Checking your session" /></div></Centered>;
  }
  if (status === "unavailable") {
    return (
      <Centered>
        <Alert tone="danger" title="The sign-in service is unavailable" live="assertive">
          Your session could not be checked. No protected data is shown. Try again shortly.
        </Alert>
      </Centered>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (allowedRole) {
    const roles = Array.isArray(allowedRole) ? allowedRole : [allowedRole];
    if (!roles.includes(user.role)) return <Navigate to={roleHomePath(user.role)} replace />;
  }
  if (requiredPermission && !user.permissions.includes(requiredPermission)) {
    return (
      <Centered>
        <section className="empty" role="alert" aria-labelledby="access-denied-title">
          <div className="empty-icon text-danger"><IconLock size={48} stroke={1.5} aria-hidden="true" /></div>
          <h1 id="access-denied-title" className="empty-title">Access denied</h1>
          <p className="empty-subtitle text-secondary">Your account does not have the permission required for this page.</p>
          <div className="empty-action"><ButtonLink to={roleHomePath(user.role)} variant="secondary">Return to your workspace</ButtonLink></div>
        </section>
      </Centered>
    );
  }
  return <>{children}</>;
};
