import React from "react";
import { IconFileCheck, IconHistory, IconQrcode, IconSearch } from "@tabler/icons-react";
import { Page } from "../../components/ui/PageHeader.tsx";
import { QuickActions } from "../../components/ssi/QuickActions.tsx";
import { ButtonLink } from "../../components/ui/Button.tsx";

export const VerifierDashboard: React.FC = () => (
  <Page
    eyebrow="Verifier workspace"
    title="Verification overview"
    actions={<ButtonLink to="/verifier/request" icon={<IconFileCheck aria-hidden="true" />}>New request</ButtonLink>}
  >
    <div className="card">
      <div className="card-body">
        <h2 className="subheader mb-3">How verification works</h2>
        <ol className="steps steps-counter steps-blue mb-0" aria-label="How verification works">
          <li className="step-item">You state a purpose and fields</li>
          <li className="step-item">The holder reviews and consents</li>
          <li className="step-item">The service checks each dimension and decides</li>
        </ol>
      </div>
    </div>
    <QuickActions actions={[
      { to: "/verifier/request", title: "Request a presentation", text: "Share a QR code and see every check.", icon: <IconQrcode size={22} />, tone: "indigo" },
      { to: "/verifier/verify", title: "Verify manually", text: "Only an explicit ACCEPTED counts as verified.", icon: <IconSearch size={22} />, tone: "teal" },
      { to: "/verifier/history", title: "History", text: "Past verification sessions.", icon: <IconHistory size={22} />, tone: "purple" },
    ]} />
  </Page>
);
