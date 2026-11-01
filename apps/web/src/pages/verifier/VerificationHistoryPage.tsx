import React from "react";
import { Page } from "../../components/ui/PageHeader.tsx";
import { NotAvailableState } from "../../components/ui/States.tsx";

export const VerificationHistoryPage: React.FC = () => (
  <Page
    eyebrow="Verifier workspace"
    title="Verification history"
    breadcrumbs={[{ label: "Verifier", to: "/verifier" }, { label: "History" }]}
  >
    <NotAvailableState
      title="History is not available yet"
      description="The service does not provide a verification history yet."
    />
  </Page>
);
