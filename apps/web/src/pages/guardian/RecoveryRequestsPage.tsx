import React from "react";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, Table } from "../../components/ui/Card.tsx";
import { ButtonLink } from "../../components/ui/Button.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { RecoveryStateBadge } from "../../components/ui/StatusBadge.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useAuth } from "../../context/AuthContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDateTime, humanize, shortenIdentifier } from "../../lib/format.ts";
import { isOpen, loadAssignments } from "./guardianData.ts";

export const RecoveryRequestsPage: React.FC = () => {
  const { user } = useAuth();
  const data = useAsync(() => loadAssignments(user?.id ?? ""), [user?.id]);
  return (
    <Page
      eyebrow="Guardian tasks"
      title="All recovery requests"
      description="Requests for wallets you guard."
      breadcrumbs={[{ label: "Guardian tasks", to: "/guardian" }, { label: "All requests" }]}
    >
      <Card flush>
        <AsyncView state={data} onRetry={data.reload} loadingLabel="Loading requests">
          {(items) => items.length === 0 ? <EmptyState title="No requests" description="No one you guard has requested recovery." /> : (
            <Table caption="Recovery requests assigned to you" stackBelow="md">
              <thead><tr><th scope="col">Wallet</th><th scope="col">Reason</th><th scope="col">State</th><th scope="col">Approvals</th><th scope="col">Requested</th><th scope="col"><span className="visually-hidden">Action</span></th></tr></thead>
              <tbody>
                {items.map(({ request }) => (
                  <tr key={request.requestId}>
                    <td data-label="Wallet"><code title={request.walletId}>{shortenIdentifier(request.walletId)}</code></td>
                    <td data-label="Reason">{humanize(request.reason)}</td>
                    <td data-label="State"><RecoveryStateBadge state={request.status} /></td>
                    <td data-label="Approvals">{request.approvalsCount ?? "?"} / {request.requiredCount ?? "?"}</td>
                    <td data-label="Requested" className="text-secondary">{formatDateTime(request.createdAt)}</td>
                    <td data-label="Action" className="text-end">
                      <ButtonLink to={`/guardian/approve/${encodeURIComponent(request.requestId)}`} size="sm" variant={isOpen(request) ? "primary" : "secondary"}>
                        {isOpen(request) ? "Review" : "View"}
                      </ButtonLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </AsyncView>
      </Card>
    </Page>
  );
};
