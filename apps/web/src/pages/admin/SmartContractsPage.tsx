import React from "react";
import { IconRefresh } from "@tabler/icons-react";
import { fetchBlockchainAnchors, fetchBlockchainContracts, fetchBlockchainStatus } from "../../api/admin.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, Stat, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { Badge, type BadgeTone } from "../../components/ui/StatusBadge.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

function anchorTone(status: string, hasTx: boolean): BadgeTone {
  if (status === "CONFIRMED" && hasTx) return "success";
  if (status === "FAILED") return "danger";
  if (status === "PENDING" || status === "SUBMITTED") return "info";
  return "neutral";
}

export const SmartContractsPage: React.FC = () => {
  const status = useAsync(() => fetchBlockchainStatus(), []);
  const contracts = useAsync(() => fetchBlockchainContracts(), []);
  const anchors = useAsync(() => fetchBlockchainAnchors(15), []);
  const reload = () => { status.reload(); contracts.reload(); anchors.reload(); };
  return (
    <Page
      eyebrow="Administration"
      title="Optional anchoring"
      description="Optional ledger for event commitments."
      breadcrumbs={[{ label: "Administration", to: "/admin" }, { label: "Optional anchoring" }]}
      actions={<Button variant="secondary" onClick={reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
    >
      <Alert tone="info">Only CONFIRMED records with a transaction hash are anchored. No personal data is written to the ledger.</Alert>
      <AsyncView state={status} onRetry={status.reload} loadingLabel="Checking ledger node">
        {(s) => (
          <Grid cols={4}>
            <Stat label="Node" value={s.connected ? <Badge tone="success">Connected</Badge> : <Badge tone="neutral">Not connected</Badge>} />
            <Stat label="Network" value={<span>{s.network}</span>} />
            <Stat label="Chain ID" value={s.chainId ?? "—"} />
            <Stat label="Latest block" value={s.currentBlockNumber ?? "—"} />
          </Grid>
        )}
      </AsyncView>
      <Card title="Contracts" flush>
        <AsyncView state={contracts} onRetry={contracts.reload} loadingLabel="Loading contract directory">
          {(items) => items.length === 0 ? <EmptyState title="No contracts configured" description="The service reports no contract addresses." /> : (
            <Table caption="Configured contracts">
              <thead><tr><th scope="col">Contract</th><th scope="col">Address</th><th scope="col">Purpose</th><th scope="col">Status</th></tr></thead>
              <tbody>
                {items.map((c) => (
                  <tr key={`${c.name}-${c.address}`}>
                    <td data-label="Contract" className="fw-medium">{c.name}</td>
                    <td data-label="Address">{c.address ? <IdentifierText value={c.address} label={`${c.name} address`} /> : "Not deployed"}</td>
                    <td data-label="Purpose" className="text-secondary">{c.purpose}</td>
                    <td data-label="Status"><Badge tone={c.deploymentVerified ? "success" : "neutral"}>{humanize(c.status)}{c.deploymentVerified ? " · verified" : ""}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </AsyncView>
      </Card>
      <Card title="Recent anchor records" flush>
        <AsyncView state={anchors} onRetry={anchors.reload} loadingLabel="Loading anchor records">
          {(items) => items.length === 0 ? <EmptyState title="No anchor records" description="Nothing has been submitted to the ledger." /> : (
            <Table caption="Anchor records" stackBelow="md">
              <thead><tr><th scope="col">Event</th><th scope="col">Status</th><th scope="col">Transaction</th><th scope="col">Created</th></tr></thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.anchorId}>
                    <td data-label="Event">{humanize(a.eventType)} · {a.contractType}</td>
                    <td data-label="Status"><Badge tone={anchorTone(a.status, Boolean(a.txHash))}>{humanize(a.status)}</Badge>{a.errorMessage ? <span className="small text-secondary"> {a.errorMessage}</span> : null}</td>
                    <td data-label="Transaction">{a.txHash ? <IdentifierText value={a.txHash} label="transaction hash" /> : "None"}{a.blockNumber ? ` · block ${a.blockNumber}` : ""}</td>
                    <td data-label="Created" className="text-secondary">{formatDateTime(a.createdAt)}</td>
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
