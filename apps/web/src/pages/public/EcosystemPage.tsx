import React from "react";
import { fetchOid4vciIssuerMetadata } from "../../api/issuance.ts";
import { fetchPublicTrustedIssuers } from "../../api/admin.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDate, humanize } from "../../lib/format.ts";

export const EcosystemPage: React.FC = () => {
  const issuers = useAsync((signal) => fetchPublicTrustedIssuers(signal), []);
  const metadata = useAsync((signal) => fetchOid4vciIssuerMetadata(signal), []);
  return (
    <Page
      eyebrow="Public directory"
      title="Trusted issuers and credential types"
      description="Trusted by this platform's policy; not a legal accreditation."
    >
      <Card title="Trust Registry" flush>
        <AsyncView state={issuers} onRetry={issuers.reload} loadingLabel="Loading trusted issuers">
          {(records) => records.length === 0 ? (
            <EmptyState title="No issuers are registered" />
          ) : (
            <Table caption="Trusted issuers" stackBelow="md">
              <thead><tr><th scope="col">Organisation</th><th scope="col">Issuer DID</th><th scope="col">Status</th><th scope="col">Credential types</th><th scope="col">Valid until</th></tr></thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td data-label="Organisation" className="fw-medium">{record.organizationName}</td>
                    <td data-label="Issuer DID"><IdentifierText value={record.issuerDid} label="issuer DID" /></td>
                    <td data-label="Status"><Badge tone={record.trustStatus.toLowerCase() === "active" ? "success" : "danger"}>{humanize(record.trustStatus.toUpperCase())}</Badge></td>
                    <td data-label="Credential types">{record.permittedCredentialTypes.map(humanize).join(", ")}</td>
                    <td data-label="Valid until">{record.validUntil ? formatDate(record.validUntil) : "No end date"}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </AsyncView>
      </Card>
      <section aria-labelledby="types-title">
        <h2 id="types-title" className="h3 mb-1">Supported credential types</h2>
        <p className="text-secondary mb-3">From <code>/.well-known/openid-credential-issuer</code>.</p>
        <AsyncView state={metadata} onRetry={metadata.reload} loadingLabel="Loading issuer metadata">
          {(value) => {
            const entries = Object.entries(value.credential_configurations_supported);
            return entries.length === 0 ? (
              <div className="card"><EmptyState title="No credential types are configured" /></div>
            ) : (
              <Grid cols={2}>
                {entries.map(([id, config]) => (
                  <Card key={id} as="article" headingLevel={3} title={config.display?.[0]?.name ?? humanize(id)} subtitle={<code>{id}</code>}>
                    <DataGrid items={[
                      { label: "Format", value: config.format ?? "Not stated" },
                      { label: "Holder binding", value: config.cryptographic_binding_methods_supported?.join(", ") ?? "Not stated" },
                      { label: "Proof types", value: Object.keys(config.proof_types_supported ?? {}).join(", ") || "Not stated" },
                    ]} />
                  </Card>
                ))}
              </Grid>
            );
          }}
        </AsyncView>
      </section>
    </Page>
  );
};
