import React from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { PublicLayout } from "../layouts/PublicLayout.tsx";
import { AppShell } from "../layouts/AppShell.tsx";
import { RoleGuard } from "./RoleGuard.tsx";
import { LoadingState } from "../components/ui/States.tsx";

const lazy = <T, K extends keyof T>(loader: () => Promise<T>, name: K) =>
  React.lazy(() => loader().then((module) => ({ default: module[name] as unknown as React.ComponentType })));

const LandingPage = lazy(() => import("../pages/public/LandingPage.tsx"), "LandingPage");
const EcosystemPage = lazy(() => import("../pages/public/EcosystemPage.tsx"), "EcosystemPage");
const ArchitectureDocsPage = lazy(() => import("../pages/public/ArchitectureDocsPage.tsx"), "ArchitectureDocsPage");
const LoginPage = lazy(() => import("../pages/public/LoginPage.tsx"), "LoginPage");
const NotFoundPage = lazy(() => import("../pages/public/NotFoundPage.tsx"), "NotFoundPage");
const OrganizationsPage = lazy(() => import("../pages/OrganizationsPage.tsx"), "OrganizationsPage");
const TrustReviewPage = lazy(() => import("../pages/admin/TrustReviewPage.tsx"), "TrustReviewPage");

const WalletDashboard = lazy(() => import("../pages/holder/WalletDashboard.tsx"), "WalletDashboard");
const CredentialDetailPage = lazy(() => import("../pages/holder/CredentialDetailPage.tsx"), "CredentialDetailPage");
const ScanQrPage = lazy(() => import("../pages/holder/ScanQrPage.tsx"), "ScanQrPage");
const PresentationConsentPage = lazy(() => import("../pages/holder/PresentationConsentPage.tsx"), "PresentationConsentPage");
const ActivityHistoryPage = lazy(() => import("../pages/holder/ActivityHistoryPage.tsx"), "ActivityHistoryPage");
const SecuritySettingsPage = lazy(() => import("../pages/holder/SecuritySettingsPage.tsx"), "SecuritySettingsPage");
const WalletBackupPage = lazy(() => import("../pages/holder/WalletBackupPage.tsx"), "WalletBackupPage");

const IssuerDashboard = lazy(() => import("../pages/issuer/IssuerDashboard.tsx"), "IssuerDashboard");
const CredentialTemplatesPage = lazy(() => import("../pages/issuer/CredentialTemplatesPage.tsx"), "CredentialTemplatesPage");
const IssueCredentialPage = lazy(() => import("../pages/issuer/IssueCredentialPage.tsx"), "IssueCredentialPage");
const RevocationRegistryPage = lazy(() => import("../pages/issuer/RevocationRegistryPage.tsx"), "RevocationRegistryPage");

const VerifierDashboard = lazy(() => import("../pages/verifier/VerifierDashboard.tsx"), "VerifierDashboard");
const CreateRequestPage = lazy(() => import("../pages/verifier/CreateRequestPage.tsx"), "CreateRequestPage");
const VerifyPresentationPage = lazy(() => import("../pages/verifier/VerifyPresentationPage.tsx"), "VerifyPresentationPage");
const VerificationHistoryPage = lazy(() => import("../pages/verifier/VerificationHistoryPage.tsx"), "VerificationHistoryPage");

const PresentRequestHandoff = lazy(() => import("../pages/holder/PresentRequestHandoff.tsx"), "PresentRequestHandoff");
const GuardianDashboard = lazy(() => import("../pages/guardian/GuardianDashboard.tsx"), "GuardianDashboard");
const RecoveryRequestsPage = lazy(() => import("../pages/guardian/RecoveryRequestsPage.tsx"), "RecoveryRequestsPage");
const ApproveRecoveryPage = lazy(() => import("../pages/guardian/ApproveRecoveryPage.tsx"), "ApproveRecoveryPage");

const AdminDashboard = lazy(() => import("../pages/admin/AdminDashboard.tsx"), "AdminDashboard");
const AdminUsersPage = lazy(() => import("../pages/admin/AdminUsersPage.tsx"), "AdminUsersPage");
const TrustRegistryPage = lazy(() => import("../pages/admin/TrustRegistryPage.tsx"), "TrustRegistryPage");
const SmartContractsPage = lazy(() => import("../pages/admin/SmartContractsPage.tsx"), "SmartContractsPage");
const AuditExplorerPage = lazy(() => import("../pages/admin/AuditExplorerPage.tsx"), "AuditExplorerPage");
const RegisterPage = lazy(() => import("../pages/public/RegisterPage.tsx"), "RegisterPage");
const AccountSecurityPage = lazy(() => import("../pages/AccountSecurityPage.tsx"), "AccountSecurityPage");
const SecurityIntelligencePage = lazy(() => import("../pages/admin/SecurityIntelligencePage.tsx"), "SecurityIntelligencePage");
const RecoveryOversightPage = lazy(() => import("../pages/admin/RecoveryOversightPage.tsx"), "RecoveryOversightPage");
const PlatformBackupPage = lazy(() => import("../pages/admin/PlatformBackupPage.tsx"), "PlatformBackupPage");

/** Legacy canonical URL /credentials/:id now resolves to the wallet route. */
const CredentialAlias: React.FC = () => {
  const { id = "" } = useParams();
  return <Navigate to={`/wallet/credentials/${encodeURIComponent(id)}`} replace />;
};

const guarded = (element: React.ReactNode, role: React.ComponentProps<typeof RoleGuard>["allowedRole"], permission?: React.ComponentProps<typeof RoleGuard>["requiredPermission"]) => (
  <RoleGuard allowedRole={role} requiredPermission={permission}>{element}</RoleGuard>
);

export const AppRoutes: React.FC = () => (
  <React.Suspense fallback={<div className="page-body"><div className="container-xl"><LoadingState label="Loading page" /></div></div>}>
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<LandingPage />} />
        <Route path="ecosystem" element={<EcosystemPage />} />
        <Route path="docs" element={<ArchitectureDocsPage />} />
      </Route>
      {/* Tabler single-page sign-in layout, without the public navbar. */}
      <Route path="login" element={<LoginPage />} />
      <Route path="register" element={<RegisterPage />} />

      <Route element={<RoleGuard><AppShell /></RoleGuard>}>
        <Route path="account/security" element={<AccountSecurityPage />} />
        <Route path="wallet" element={guarded(<WalletDashboard />, "HOLDER", "wallets:read")} />
        <Route path="wallet/credentials/:id" element={guarded(<CredentialDetailPage />, "HOLDER", "wallets:credentials:read")} />
        <Route path="wallet/scan" element={guarded(<ScanQrPage />, "HOLDER", "wallets:read")} />
        <Route path="wallet/present" element={guarded(<PresentRequestHandoff />, "HOLDER", "wallets:read")} />
        <Route path="wallet/consent" element={guarded(<PresentationConsentPage />, "HOLDER", "presentations:create")} />
        <Route path="wallet/activity" element={guarded(<ActivityHistoryPage />, "HOLDER", "presentations:read")} />
        <Route path="wallet/security" element={guarded(<SecuritySettingsPage />, "HOLDER", "wallet:key:read")} />
        <Route path="wallet/backup" element={guarded(<WalletBackupPage />, "HOLDER", "wallets:backup")} />
        <Route path="credentials/:id" element={guarded(<CredentialAlias />, "HOLDER")} />
        <Route path="consent/presentation" element={guarded(<PresentationConsentPage />, "HOLDER", "presentations:create")} />

        <Route path="issuer" element={guarded(<IssuerDashboard />, "ISSUER", "credentials:sign")} />
        <Route path="issuer/templates" element={guarded(<CredentialTemplatesPage />, "ISSUER", "credentials:sign")} />
        <Route path="issuer/issue" element={guarded(<IssueCredentialPage />, "ISSUER", "credentials:sign")} />
        <Route path="issuer/revocations" element={guarded(<RevocationRegistryPage />, "ISSUER", "credentials:revoke")} />

        <Route path="verifier" element={guarded(<VerifierDashboard />, "VERIFIER", "presentations:verify")} />
        <Route path="verifier/request" element={guarded(<CreateRequestPage />, "VERIFIER", "presentations:verify")} />
        <Route path="verifier/verify" element={guarded(<VerifyPresentationPage />, "VERIFIER", "presentations:verify")} />
        <Route path="verifier/history" element={guarded(<VerificationHistoryPage />, "VERIFIER", "presentations:read")} />

        {/* Guardian duties are an assignment on a Holder account, not a separate Identity role. */}
        <Route path="guardian" element={guarded(<GuardianDashboard />, "HOLDER")} />
        <Route path="guardian/requests" element={guarded(<RecoveryRequestsPage />, "HOLDER")} />
        <Route path="guardian/approve/:id" element={guarded(<ApproveRecoveryPage />, "HOLDER")} />

        <Route path="admin" element={guarded(<AdminDashboard />, "ADMIN", "admin:operations:read")} />
        <Route path="admin/users" element={guarded(<AdminUsersPage />, "ADMIN", "admin:users:read")} />
        <Route path="admin/trust-registry" element={guarded(<TrustRegistryPage />, "ADMIN", "admin:operations:read")} />
        <Route path="admin/contracts" element={guarded(<SmartContractsPage />, "ADMIN", "admin:operations:read")} />
        <Route path="admin/audit" element={guarded(<AuditExplorerPage />, "ADMIN", "admin:operations:read")} />
        <Route path="admin/fraud-monitor" element={<Navigate to="/admin/intelligence" replace />} />
        <Route path="admin/intelligence" element={guarded(<SecurityIntelligencePage />, "ADMIN", "admin:operations:read")} />
        <Route path="admin/recovery" element={guarded(<RecoveryOversightPage />, "ADMIN", "admin:operations:read")} />
        <Route path="admin/backups" element={guarded(<PlatformBackupPage />, "ADMIN", "admin:backup:read")} />
        <Route path="admin/trust-review" element={guarded(<TrustReviewPage />, "ADMIN", "trust-review:decide")} />
        {/* Memberships are per organization and re-checked by the server; any signed-in person may have them. */}
        <Route path="organizations" element={<OrganizationsPage />} />
      </Route>

      <Route element={<PublicLayout />}>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  </React.Suspense>
);
