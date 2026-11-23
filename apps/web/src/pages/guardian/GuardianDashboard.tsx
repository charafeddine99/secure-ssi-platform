import React from "react";
import { IconChecklist, IconClockHour4, IconRefresh, IconUsers } from "@tabler/icons-react";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, Stat } from "../../components/ui/Card.tsx";
import { Button, ButtonLink } from "../../components/ui/Button.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { RecoveryStateBadge } from "../../components/ui/StatusBadge.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { useAuth } from "../../context/AuthContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";
import { isActive, isOpen, loadAssignments } from "./guardianData.ts";
import { GuardianKeysCard, InvitationsCard } from "./GuardianEnrollment.tsx";
import { RecoveryNotificationsCard } from "../../components/ssi/RecoveryNotificationsCard.tsx";

export const GuardianDashboard: React.FC = () => {
  const { user } = useAuth();
  const data = useAsync(() => loadAssignments(user?.id ?? ""), [user?.id]);
  const [keysVersion, setKeysVersion] = React.useState(0);
  return (
    <Page
      eyebrow="Guardian tasks"
      title="Recovery requests you can decide"
      description="Confirm with the person before approving."
      actions={<Button variant="secondary" onClick={data.reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
    >
      <InvitationsCard onChanged={() => { data.reload(); setKeysVersion((value) => value + 1); }} />
      <AsyncView state={data} onRetry={data.reload} loadingLabel="Loading guardian assignments" errorTitle="The recovery service could not be reached">
        {(items) => {
          const open = items.filter((a) => isOpen(a.request));
          return (
            <>
              <Grid cols={3}>
                <Stat label="Awaiting your decision" value={open.length} icon={<IconChecklist size={20} />} tone="orange" />
                <Stat label="In progress" value={items.filter((a) => isActive(a.request)).length} hint="Includes time-lock" icon={<IconClockHour4 size={20} />} tone="azure" />
                <Stat label="All assignments" value={items.length} icon={<IconUsers size={20} />} tone="secondary" />
              </Grid>
              <Card title="Awaiting your decision" flush footer={<ButtonLink to="/guardian/requests" variant="ghost" size="sm">All requests</ButtonLink>}>
                {open.length === 0 ? <EmptyState title="Nothing to decide" description="You will see a request here when someone you guard starts recovery." /> : (
                  <ul className="list-group list-group-flush">
                    {open.map(({ request, guardian }) => (
                      <li key={request.requestId} className="list-group-item">
                        <div className="row align-items-center g-3">
                          <div className="col min-w-0">
                            <div className="d-flex flex-wrap align-items-center gap-2 fw-medium">{humanize(request.reason)} <RecoveryStateBadge state={request.status} /></div>
                            <div className="small text-secondary mt-1">Wallet <IdentifierText value={request.walletId} label="wallet" copy={false} /> · you are listed as {guardian.displayName} · closes {formatDateTime(request.approvalExpiresAt)}</div>
                          </div>
                          <div className="col-auto">
                            <ButtonLink to={`/guardian/approve/${encodeURIComponent(request.requestId)}`} size="sm">Review</ButtonLink>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </>
          );
        }}
      </AsyncView>
      <GuardianKeysCard key={keysVersion} />
      <RecoveryNotificationsCard />
    </Page>
  );
};
