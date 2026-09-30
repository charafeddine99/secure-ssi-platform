import React from "react";
import { Routes, Route } from "react-router-dom";
import { RootLayout } from "../layouts/RootLayout";
import { PublicLayout } from "../layouts/PublicLayout";
import { HolderLayout } from "../layouts/HolderLayout";
import { InstitutionalLayout } from "../layouts/InstitutionalLayout";
import { RoleGuard } from "./RoleGuard";

// Loading placeholder for async route transitions
const PageLoader: React.FC = () => (
  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "350px" }}>
    <div style={{ padding: "1.5rem 2rem", borderRadius: "10px", background: "rgba(30, 41, 59, 0.7)", border: "1px solid rgba(255,255,255,0.1)", color: "#94a3b8", fontSize: "0.95rem" }}>
      Yükleniyor...
    </div>
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
            <RoleGuard allowedRole="HOLDER" requireAuth={false}>
              <HolderLayout />
            </RoleGuard>
          }
        >
          <Route index element={<WalletDashboard />} />
          <Route path="credentials/:id" element={<CredentialDetailPage />} />
          <Route path="scan" element={<ScanQrPage />} />
          <Route path="consent" element={<PresentationConsentPage />} />
          <Route path="activity" element={<ActivityHistoryPage />} />
          <Route path="security" element={<SecuritySettingsPage />} />
        </Route>

        {/* 3. Issuer Portal Routes */}
        <Route
          path="issuer"
          element={
            <RoleGuard allowedRole="ISSUER" requireAuth={false}>
              <InstitutionalLayout />
            </RoleGuard>
          }
        >
          <Route index element={<IssuerDashboard />} />
          <Route path="templates" element={<CredentialTemplatesPage />} />
          <Route path="issue" element={<IssueCredentialPage />} />
          <Route path="revocations" element={<RevocationRegistryPage />} />
        </Route>

        {/* 4. Verifier Portal Routes */}
        <Route
          path="verifier"
          element={
            <RoleGuard allowedRole="VERIFIER" requireAuth={false}>
              <InstitutionalLayout />
            </RoleGuard>
          }
        >
          <Route index element={<VerifierDashboard />} />
          <Route path="request" element={<CreateRequestPage />} />
          <Route path="verify" element={<VerifyPresentationPage />} />
          <Route path="history" element={<VerificationHistoryPage />} />
        </Route>

        {/* 5. Guardian Portal Routes */}
        <Route
          path="guardian"
          element={
            <RoleGuard allowedRole="GUARDIAN" requireAuth={false}>
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
            <RoleGuard allowedRole="ADMIN" requireAuth={false}>
              <InstitutionalLayout />
            </RoleGuard>
          }
        >
          <Route index element={<AdminDashboard />} />
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
