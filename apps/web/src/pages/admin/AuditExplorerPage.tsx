import React from "react";
import { IconDownload, IconRefresh } from "@tabler/icons-react";
import { fetchAuditIntegrity, fetchAuditLogs, type AuditLogEntry } from "../../api/admin.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { SelectField, TextField } from "../../components/ui/Field.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { Badge, type BadgeTone } from "../../components/ui/StatusBadge.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDateTime, humanize, shortenIdentifier } from "../../lib/format.ts";
import { auditCsv } from "./auditCsv.ts";

const EVENT_FILTERS = ["ALL", "CREDENTIAL", "PRESENTATION", "WALLET", "RECOVERY", "TRUST", "AUTH", "QUARANTINE"];

/** The Identity Service reports an integer advisory score (0–100). */
function riskTone(score: number | null): BadgeTone {
  if (score === null) return "neutral";
  if (score >= 70) return "danger";
  if (score >= 40) return "warning";
  return "success";
}

export const AuditExplorerPage: React.FC = () => {
  const [filter, setFilter] = React.useState("ALL");
  const [search, setSearch] = React.useState("");
  const [expanded, setExpanded] = React.useState<string | null>(null);
  // Categories are filtered locally: the service only accepts exact event-type values.
  const logs = useAsync(() => fetchAuditLogs(undefined, 150), []);
  const integrity = useAsync(fetchAuditIntegrity, []);

  const visible = (rows: AuditLogEntry[]) => {
    const term = search.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesFilter = filter === "ALL" || row.eventType.toUpperCase().includes(filter);
      const matchesSearch = !term || [row.eventType, row.actorDid, row.targetWallet ?? ""].some((v) => v.toLowerCase().includes(term));
      return matchesFilter && matchesSearch;
    });
  };

  const exportCsv = (rows: AuditLogEntry[]) => {
    const blob = new Blob([auditCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-events-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Page
        eyebrow="Administration"
        title="Audit log"
        description="Security events. Risk scores are advisory."
        breadcrumbs={[{ label: "Administration", to: "/admin" }, { label: "Audit log" }]}
        actions={<Button variant="secondary" onClick={logs.reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
    >
      {integrity.status === "success" && (
        <Alert tone={integrity.data.status === "INTACT" ? "success" : "danger"} title={integrity.data.status === "INTACT" ? "Audit chain intact" : "Audit chain check failed"} className="mb-3">
          {integrity.data.checked} events checked; {integrity.data.unchained} older events are outside the chain. This detects edits and removed events, but not the removal of the newest events.
        </Alert>
      )}
      <Card
        title="Events"
        actions={logs.status === "success" && logs.data.length > 0
          ? <Button size="sm" variant="secondary" onClick={() => exportCsv(visible(logs.data))} icon={<IconDownload aria-hidden="true" />}>Export shown rows (CSV)</Button>
          : undefined}
        flush
      >
        <div className="card-body border-bottom py-3">
          <div className="row g-3">
            <SelectField groupClassName="col-md-4 mb-0" label="Event category" value={filter} onChange={(e) => setFilter(e.target.value)}>
              {EVENT_FILTERS.map((f) => <option key={f} value={f}>{f === "ALL" ? "All events" : humanize(f)}</option>)}
            </SelectField>
            <TextField groupClassName="col-md-8 mb-0" label="Search in loaded events" type="search" value={search} onChange={(e) => setSearch(e.target.value)} hint="Matches event type, actor DID or wallet." />
          </div>
        </div>
        <AsyncView state={logs} onRetry={logs.reload} loadingLabel="Loading audit events" errorTitle="Audit events are unavailable">
          {(rows) => {
            const shown = visible(rows);
            if (shown.length === 0) return <EmptyState title="No matching events" description={rows.length ? "Change the filter or search term." : "The audit store returned no events."} />;
            return (
              <Table caption="Audit events, newest first" stackBelow="md">
                <thead><tr><th scope="col">Time</th><th scope="col">Event</th><th scope="col">Actor</th><th scope="col">Risk</th><th scope="col"><span className="visually-hidden">Details</span></th></tr></thead>
                <tbody>
                  {shown.map((row) => (
                    <React.Fragment key={row.id}>
                      <tr>
                        <td data-label="Time" className="text-secondary text-nowrap">{formatDateTime(row.createdAt)}</td>
                        <td data-label="Event" className="fw-medium">{humanize(row.eventType)}</td>
                        <td data-label="Actor"><code title={row.actorDid}>{row.actorDid ? shortenIdentifier(row.actorDid) : "—"}</code></td>
                        <td data-label="Risk"><Badge tone={riskTone(row.riskScore)}>{row.riskScore === null ? "Not scored" : `${Math.round(row.riskScore)} / 100`}</Badge></td>
                        <td data-label="Details" className="text-end">
                          <Button size="sm" variant="ghost" aria-expanded={expanded === row.id} aria-controls={`audit-${row.id}`} onClick={() => setExpanded(expanded === row.id ? null : row.id)}>
                            {expanded === row.id ? "Hide" : "Details"}
                          </Button>
                        </td>
                      </tr>
                      {expanded === row.id && (
                        <tr id={`audit-${row.id}`}>
                          <td colSpan={5}><pre className="code-pane" tabIndex={0}>{JSON.stringify({ targetWallet: row.targetWallet, details: row.details }, null, 2)}</pre></td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </Table>
            );
          }}
        </AsyncView>
      </Card>
    </Page>
  );
};
