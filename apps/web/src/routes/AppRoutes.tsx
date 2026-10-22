import React from "react";
import { Routes, Route } from "react-router-dom";
import { RootLayout } from "../layouts/RootLayout";
import { PublicLayout } from "../layouts/PublicLayout";
import { HolderLayout } from "../layouts/HolderLayout";
import { InstitutionalLayout } from "../layouts/InstitutionalLayout";
import { RoleGuard } from "./RoleGuard";

// Loading placeholder for async route transitions
const PageLoader: React.FC = () => (
  <div className="page-loader" role="status" aria-live="polite">
    <div className="page-loader__message">Loading</div>
  </div>
);

// Public Pages (Lazy)
const LandingPage = React.lazy(() => import("../pages/public/LandingPage").then(m => ({ default: m.LandingPage })));
const EcosystemPage = React.lazy(() => import("../pages/public/EcosystemPage").then(m => ({ default: m.EcosystemPage })));
const ArchitectureDocsPage = React.lazy(() => import("../pages/public/ArchitectureDocsPage").then(m => ({ default: m.ArchitectureDocsPage })));
const AuthPage = React.lazy(() => import("../components/auth/AuthPage").then(m => ({ default: m.AuthPage })));
const NotFoundPage = React.lazy(() => import("../pages/public/NotFoundPage").then(m => ({ default: m.NotFoundPage })));

// Holder Pages (Lazy)
const WalletDashboard = React.lazy(() => import("../pages/holder/WalletDashboard").then(m => ({ default: m.WalletDashboard })));
const CredentialDetailPage = React.lazy(() => import("../pages/holder/CredentialDetailPage").then(m => ({ default: m.CredentialDetailPage })));
const ScanQrPage = React.lazy(() => import("../pages/holder/ScanQrPage").then(m => ({ default: m.ScanQrPage })));
const PresentationConsentPage = React.lazy(() => import("../pages/holder/PresentationConsentPage").then(m => ({ default: m.PresentationConsentPage })));
const ActivityHistoryPage = React.lazy(() => import("../pages/holder/ActivityHistoryPage").then(m => ({ default: m.ActivityHistoryPage })));
const SecuritySettingsPage = React.lazy(() => import("../pages/holder/SecuritySettingsPage").then(m => ({ default: m.SecuritySettingsPage })));

// Issuer Pages (Lazy)
const IssuerDashboard = React.lazy(() => import("../pages/issuer/IssuerDashboard").then(m => ({ default: m.IssuerDashboard })));
const CredentialTemplatesPage = React.lazy(() => import("../pages/issuer/CredentialTemplatesPage").then(m => ({ default: m.CredentialTemplatesPage })));
const IssueCredentialPage = React.lazy(() => import("../pages/issuer/IssueCredentialPage").then(m => ({ default: m.IssueCredentialPage })));
const RevocationRegistryPage = React.lazy(() => import("../pages/issuer/RevocationRegistryPage").then(m => ({ default: m.RevocationRegistryPage })));

// Verifier Pages (Lazy)
const VerifierDashboard = React.lazy(() => import("../pages/verifier/VerifierDashboard").then(m => ({ default: m.VerifierDashboard })));
const CreateRequestPage = React.lazy(() => import("../pages/verifier/CreateRequestPage").then(m => ({ default: m.CreateRequestPage })));
const VerifyPresentationPage = React.lazy(() => import("../pages/verifier/VerifyPresentationPage").then(m => ({ default: m.VerifyPresentationPage })));
const VerificationHistoryPage = React.lazy(() => import("../pages/verifier/VerificationHistoryPage").then(m => ({ default: m.VerificationHistoryPage })));

// Guardian Pages (Lazy)
const GuardianDashboard = React.lazy(() => import("../pages/guardian/GuardianDashboard").then(m => ({ default: m.GuardianDashboard })));
const RecoveryRequestsPage = React.lazy(() => import("../pages/guardian/RecoveryRequestsPage").then(m => ({ default: m.RecoveryRequestsPage })));
const ApproveRecoveryPage = React.lazy(() => import("../pages/guardian/ApproveRecoveryPage").then(m => ({ default: m.ApproveRecoveryPage })));

// Admin Pages (Lazy)
const AdminDashboard = React.lazy(() => import("../pages/admin/AdminDashboard").then(m => ({ default: m.AdminDashboard })));
const SmartContractsPage = React.lazy(() => import("../pages/admin/SmartContractsPage").then(m => ({ default: m.SmartContractsPage })));
const AuditExplorerPage = React.lazy(() => import("../pages/admin/AuditExplorerPage").then(m => ({ default: m.AuditExplorerPage })));
const AiFraudMonitorPage = React.lazy(() => import("../pages/admin/AiFraudMonitorPage").then(m => ({ default: m.AiFraudMonitorPage })));
const AdminUsersPage = React.lazy(() => import("../pages/admin/AdminUsersPage").then(m => ({ default: m.AdminUsersPage })));

export const AppRoutes: React.FC = () => {
  return (
    <React.Suspense fallback={<PageLoader />}>
      <Routes>
      <Route path="/" element={<RootLayout />}>
        {/* 1. Public Pages */}
        <Route element={<PublicLayout />}>
          <Route index element={<LandingPage />} />
          <Route path="ecosystem" element={<EcosystemPage />} />
          <Route path="docs" element={<ArchitectureDocsPage />} />
          <Route path="login" element={<AuthPage />} />
        </Route>

        {/* 2. Holder Wallet Routes */}
        <Route
          path="wallet"
          element={
            <RoleGuard allowedRole="HOLDER" requiredPermission="wallets:read" requireAuth={true}>
              <HolderLayout />
            </RoleGuard>
          }
        >
          <Route index element={<WalletDashboard />} />
          <Route path="credentials/:id" element={<RoleGuard allowedRole="HOLDER" requiredPermission="wallets:credentials:read"><CredentialDetailPage /></RoleGuard>} />
          <Route path="scan" element={<RoleGuard allowedRole="HOLDER" requiredPermission="wallets:read"><ScanQrPage /></RoleGuard>} />
          <Route path="consent" element={<RoleGuard allowedRole="HOLDER" requiredPermission="presentations:create"><PresentationConsentPage /></RoleGuard>} />
          <Route path="activity" element={<RoleGuard allowedRole="HOLDER" requiredPermission="presentations:read"><ActivityHistoryPage /></RoleGuard>} />
          <Route path="security" element={<RoleGuard allowedRole="HOLDER" requiredPermission="wallet:key:read"><SecuritySettingsPage /></RoleGuard>} />
        </Route>

        {/* 2b. Direct Holder Canonical URLs */}
        <Route
          path="credentials/:id"
          element={
            <RoleGuard allowedRole="HOLDER" requiredPermission="wallets:credentials:read" requireAuth={true}>
              <HolderLayout />
            </RoleGuard>
          }
        >
          <Route index element={<CredentialDetailPage />} />
        </Route>
        <Route
          path="consent/presentation"
          element={
            <RoleGuard allowedRole="HOLDER" requiredPermission="presentations:create" requireAuth={true}>
              <HolderLayout />
            </RoleGuard>
          }
        >
          <Route index element={<PresentationConsentPage />} />
        </Route>

        {/* 3. Issuer Portal Routes */}
        <Route
          path="issuer"
          element={
            <RoleGuard allowedRole="ISSUER" requireAuth={true}>
              <InstitutionalLayout />
            </RoleGuard>
          }
        >
          <Route index element={<RoleGuard allowedRole="ISSUER" requiredPermission="credentials:sign"><IssuerDashboard /></RoleGuard>} />
          <Route path="templates" element={<RoleGuard allowedRole="ISSUER" requiredPermission="credentials:sign"><CredentialTemplatesPage /></RoleGuard>} />
          <Route path="issue" element={<RoleGuard allowedRole="ISSUER" requiredPermission="credentials:sign"><IssueCredentialPage /></RoleGuard>} />
          <Route path="revocations" element={<RoleGuard allowedRole="ISSUER" requiredPermission="credentials:revoke"><RevocationRegistryPage /></RoleGuard>} />
        </Route>

        {/* 4. Verifier Portal Routes */}
        <Route
          path="verifier"
          element={
            <RoleGuard allowedRole="VERIFIER" requireAuth={true}>
              <InstitutionalLayout />
            </RoleGuard>
          }
        >
          <Route index element={<RoleGuard allowedRole="VERIFIER" requiredPermission="presentations:verify"><VerifierDashboard /></RoleGuard>} />
          <Route path="request" element={<RoleGuard allowedRole="VERIFIER" requiredPermission="presentation-challenges:create"><CreateRequestPage /></RoleGuard>} />
          <Route path="verify" element={<RoleGuard allowedRole="VERIFIER" requiredPermission="presentations:verify"><VerifyPresentationPage /></RoleGuard>} />
          <Route path="history" element={<RoleGuard allowedRole="VERIFIER" requiredPermission="presentations:read"><VerificationHistoryPage /></RoleGuard>} />
        </Route>

        {/* Guardian recovery is an assigned Holder capability, not a global Identity role. */}
        <Route
          path="guardian"
          element={
            <RoleGuard allowedRole="HOLDER" requireAuth={true}>
              <InstitutionalLayout />
            </RoleGuard>
          }
        >
          <Route index element={<GuardianDashboard />} />
          <Route path="requests" element={<RecoveryRequestsPage />} />
          <Route path="approve/:id" element={<ApproveRecoveryPage />} />
        </Route>

        {/* 6. Admin Portal Routes */}
        <Route
          path="admin"
          element={
            <RoleGuard allowedRole="ADMIN" requiredPermission="admin:operations:read" requireAuth={true}>
              <InstitutionalLayout />
            </RoleGuard>
          }
        >
          <Route index element={<AdminDashboard />} />
          <Route path="users" element={<RoleGuard allowedRole="ADMIN" requiredPermission="admin:users:read"><AdminUsersPage /></RoleGuard>} />
          <Route path="contracts" element={<SmartContractsPage />} />
          <Route path="audit" element={<AuditExplorerPage />} />
          <Route path="fraud-monitor" element={<AiFraudMonitorPage />} />
        </Route>

        {/* 7. Catch-all / 404 Route */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
    </React.Suspense>
  );
};
