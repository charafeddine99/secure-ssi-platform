import React from "react";
import { IconArrowRight } from "@tabler/icons-react";
import { fetchOid4vciIssuerMetadata } from "../../api/issuance.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid } from "../../components/ui/Card.tsx";
import { ButtonLink } from "../../components/ui/Button.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { humanize } from "../../lib/format.ts";

export const CredentialTemplatesPage: React.FC = () => {
  const metadata = useAsync((signal) => fetchOid4vciIssuerMetadata(signal), []);
  return (
    <Page
      eyebrow="Issuer workspace"
      title="Credential types"
      description="Types published in the issuer metadata."
      breadcrumbs={[{ label: "Issuer", to: "/issuer" }, { label: "Credential types" }]}
    >
      <AsyncView state={metadata} onRetry={metadata.reload} loadingLabel="Loading issuer metadata" errorTitle="Issuer metadata could not be loaded">
        {(data) => {
          const entries = Object.entries(data.credential_configurations_supported);
          if (entries.length === 0) return <div className="card"><EmptyState title="No credential types published" description="The issuer metadata lists no credential configurations." /></div>;
          return (
            <Grid cols={2}>
              {entries.map(([id, config]) => (
                <Card
                  key={id}
                  as="article"
                  headingLevel={2}
                  title={config.display?.[0]?.name ?? humanize(id)}
                  subtitle={<code>{id}</code>}
                  actions={<Badge tone="brand">{config.format ?? "unknown format"}</Badge>}
                  footer={<ButtonLink to={`/issuer/issue?credentialConfigurationId=${encodeURIComponent(id)}`} variant="secondary" size="sm" icon={<IconArrowRight aria-hidden="true" />}>Create offer</ButtonLink>}
                >
                  <DataGrid items={[
                    { label: "Types", value: config.credential_definition?.type?.join(", ") ?? "Not stated" },
                    { label: "Holder binding", value: config.cryptographic_binding_methods_supported?.join(", ") ?? "Not stated" },
                    { label: "Signing", value: config.credential_signing_alg_values_supported?.join(", ") ?? "Not stated" },
                    { label: "Proof types", value: Object.keys(config.proof_types_supported ?? {}).join(", ") || "None" },
                  ]} />
                </Card>
              ))}
            </Grid>
          );
        }}
      </AsyncView>
      <p className="small text-secondary mb-0">Credential issuer: <code>{metadata.status === "success" ? metadata.data.credential_issuer : "…"}</code></p>
    </Page>
  );
};
