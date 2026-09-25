import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { RootLayout } from "../layouts/RootLayout";
import { PublicLayout } from "../layouts/PublicLayout";
import { HolderLayout } from "../layouts/HolderLayout";
import { InstitutionalLayout } from "../layouts/InstitutionalLayout";
import { RoleGuard } from "./RoleGuard";

// Public Pages
import { LandingPage } from "../pages/public/LandingPage";
import { EcosystemPage } from "../pages/public/EcosystemPage";
import { ArchitectureDocsPage } from "../pages/public/ArchitectureDocsPage";
import { NotFoundPage } from "../pages/public/NotFoundPage";

// Holder Pages
import { WalletDashboard } from "../pages/holder/WalletDashboard";
import { CredentialDetailPage } from "../pages/holder/CredentialDetailPage";
import { ScanQrPage } from "../pages/holder/ScanQrPage";
import { PresentationConsentPage } from "../pages/holder/PresentationConsentPage";
import { ActivityHistoryPage } from "../pages/holder/ActivityHistoryPage";
import { SecuritySettingsPage } from "../pages/holder/SecuritySettingsPage";

// Issuer Pages
import { IssuerDashboard } from "../pages/issuer/IssuerDashboard";
import { CredentialTemplatesPage } from "../pages/issuer/CredentialTemplatesPage";
import { IssueCredentialPage } from "../pages/issuer/IssueCredentialPage";
import { RevocationRegistryPage } from "../pages/issuer/RevocationRegistryPage";

// Verifier Pages
import { VerifierDashboard } from "../pages/verifier/VerifierDashboard";
import { CreateRequestPage } from "../pages/verifier/CreateRequestPage";
import { VerifyPresentationPage } from "../pages/verifier/VerifyPresentationPage";
import { VerificationHistoryPage } from "../pages/verifier/VerificationHistoryPage";

// Guardian Pages
import { GuardianDashboard } from "../pages/guardian/GuardianDashboard";
import { RecoveryRequestsPage } from "../pages/guardian/RecoveryRequestsPage";
import { ApproveRecoveryPage } from "../pages/guardian/ApproveRecoveryPage";

// Admin Pages
import { AdminDashboard } from "../pages/admin/AdminDashboard";
import { SmartContractsPage } from "../pages/admin/SmartContractsPage";
import { AuditExplorerPage } from "../pages/admin/AuditExplorerPage";
import { AiFraudMonitorPage } from "../pages/admin/AiFraudMonitorPage";

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<RootLayout />}>
        {/* 1. Public Pages */}
        <Route element={<PublicLayout />}>
          <Route index element={<LandingPage />} />
          <Route path="ecosystem" element={<EcosystemPage />} />
          <Route path="docs" element={<ArchitectureDocsPage />} />
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
  );
};
