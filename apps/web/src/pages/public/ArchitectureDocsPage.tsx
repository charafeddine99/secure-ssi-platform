import React from "react";
import { Card } from "../../components/ui/Card.tsx";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";

const SERVICES = [
  { name: "API Gateway", text: "Single entry point with header stripping, payload limits and rate limiting." },
  { name: "Identity Service", text: "Wallets, issuance, presentation, signatures, status lists and the Trust Registry." },
  { name: "Recovery Service", text: "M-of-N guardian approval with a time-lock, then key rotation." },
  { name: "Risk Service", text: "Rule-based, advisory risk signal." },
];

export const ArchitectureDocsPage: React.FC = () => (
  <Page eyebrow="Documentation" title="How the platform works">
    <Grid cols={2}>
      {SERVICES.map((service) => (
        <Card key={service.name} as="article" headingLevel={2} title={service.name}>
          <p className="text-secondary mb-0">{service.text}</p>
        </Card>
      ))}
    </Grid>
    <Card title="Verification is a set of separate checks">
      <p className="text-secondary mb-0">Signature, issuer trust, holder binding, validity, revocation and request binding are checked one by one. Only the backend decides.</p>
    </Card>
    <Card title="Privacy boundaries" flush>
      <div className="list-group list-group-flush">
        <div className="list-group-item">No personal data or credentials are written to a ledger.</div>
        <div className="list-group-item">Presentations share the full signed credential.</div>
        <div className="list-group-item">Status checks can reveal which credential is checked.</div>
      </div>
    </Card>
  </Page>
);
