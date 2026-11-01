import React from "react";
import { IconCpu, IconDatabase, IconRefresh, IconShieldCheck } from "@tabler/icons-react";
import { fetchFraudStats } from "../../api/admin.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, Stat } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { RiskStatusValue } from "./RiskStatusValue.tsx";

export const AiFraudMonitorPage: React.FC = () => {
  const stats = useAsync(() => fetchFraudStats(), []);
  return (
    <Page
      eyebrow="Administration"
      title="Risk engine"
      description="Advisory risk service status."
      breadcrumbs={[{ label: "Administration", to: "/admin" }, { label: "Risk engine" }]}
      actions={<Button variant="secondary" onClick={stats.reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
    >
      <Alert tone="warning" title="Advisory only">
        Never replaces trust, validity or revocation checks.
      </Alert>
      <AsyncView state={stats} onRetry={stats.reload} loadingLabel="Loading risk service status" errorTitle="Risk service status is unavailable">
        {(s) => (
          <>
            <Grid cols={3}>
              <Stat label="Engine" value={<RiskStatusValue as="strong" value={s.model_type} />} hint={`Version ${s.model_version || "not reported"}`} icon={<IconCpu size={20} />} tone="secondary" />
              <Stat label="Model status" value={<RiskStatusValue as="strong" value={s.model_status} />} hint={<>Evaluation: <RiskStatusValue value={s.evaluation_status} /></>} icon={<IconShieldCheck size={20} />} tone="secondary" />
              <Stat label="Data scope" value={<RiskStatusValue as="strong" value={s.dataset_label} />} hint={`Advisory only: ${s.advisory_only ? "yes" : "not confirmed"}`} icon={<IconDatabase size={20} />} tone="secondary" />
            </Grid>
            <Card title="Reported signals" flush>
              {s.risk_signals.length === 0 ? <EmptyState title="No signals reported" description="The risk service responded and reported no signals." /> : (
                <ul className="list-group list-group-flush">{s.risk_signals.map((signal) => <li key={signal} className="list-group-item"><RiskStatusValue value={signal} /></li>)}</ul>
              )}
            </Card>
          </>
        )}
      </AsyncView>
    </Page>
  );
};
