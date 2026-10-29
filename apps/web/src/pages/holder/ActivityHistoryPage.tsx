import React from "react";
import { Page } from "../../components/ui/PageHeader.tsx";
import { NotAvailableState } from "../../components/ui/States.tsx";

export const ActivityHistoryPage: React.FC = () => (
  <Page
    eyebrow="Holder wallet"
    title="Activity"
    breadcrumbs={[{ label: "Wallet", to: "/wallet" }, { label: "Activity" }]}
  >
    <NotAvailableState
      title="Holder activity history is not available yet"
      description="The service does not provide a holder history yet."
    />
  </Page>
);
