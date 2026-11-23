import React from "react";
import { IconBuildingBank, IconCpu, IconHistory, IconRefresh, IconUsers } from "@tabler/icons-react";
import { fetchAuditLogs, fetchDatabaseStats, fetchGatewayStatus, type AuditLogEntry } from "../../api/admin.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, Stat, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { QuickActions } from "../../components/ssi/QuickActions.tsx";
import { BarChart, DonutChart, type ChartDatum } from "../../components/ui/Charts.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { Badge, type BadgeTone } from "../../components/ui/StatusBadge.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { humanize } from "../../lib/format.ts";

function healthTone(value: string): BadgeTone {
  const v = value.toUpperCase();
  if (["UP", "HEALTHY", "OK", "ONLINE", "OPERATIONAL", "OPTIMAL", "CONNECTED"].includes(v)) return "success";
  if (["DEGRADED", "PARTIAL"].includes(v)) return "warning";
  if (["DOWN", "UNHEALTHY", "OFFLINE", "ERROR", "UNAVAILABLE", "UNREACHABLE"].includes(v)) return "danger";
  return "neutral";
}

/** Events per calendar day for the last `days` days, oldest first. */
function eventsPerDay(rows: AuditLogEntry[], days = 14): ChartDatum[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const day = row.createdAt.slice(0, 10);
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }
  const out: ChartDatum[] = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    out.push({ label: d.toLocaleDateString(undefined, { day: "2-digit", month: "short" }), value: counts.get(key) ?? 0 });
  }
  return out;
}

/** Five most frequent event types, the rest grouped as "Other". */
function eventMix(rows: AuditLogEntry[]): ChartDatum[] {
  const counts = new Map<string, number>();
  for (const row of rows) counts.set(row.eventType, (counts.get(row.eventType) ?? 0) + 1);
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const top = sorted.slice(0, 5).map(([label, value]) => ({ label: humanize(label), value }));
  const rest = sorted.slice(5).reduce((sum, [, value]) => sum + value, 0);
  return rest > 0 ? [...top, { label: "Other", value: rest }] : top;
}

const DOT: Record<BadgeTone, string> = { success: "status-green", warning: "status-yellow", danger: "status-red", info: "status-azure", neutral: "status-secondary", brand: "status-indigo" };

export const AdminDashboard: React.FC = () => {
  const gateway = useAsync(() => fetchGatewayStatus(), []);
  const persistence = useAsync(() => fetchDatabaseStats(), []);
  const audit = useAsync(() => fetchAuditLogs(undefined, 200), []);
  const reload = () => { gateway.reload(); persistence.reload(); audit.reload(); };
  return (
    <Page
      eyebrow="Administration"
      title="Platform health"
      description="Live service and storage status."
      actions={<Button variant="secondary" onClick={reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
    >
      <QuickActions actions={[
        { to: "/admin/trust-registry", title: "Trust registry", text: "Issuers verifiers accept.", icon: <IconBuildingBank size={22} />, tone: "indigo" },
        { to: "/admin/users", title: "Users & issuer scope", text: "Link issuers to institutions.", icon: <IconUsers size={22} />, tone: "teal" },
        { to: "/admin/audit", title: "Audit log", text: "Security-relevant events.", icon: <IconHistory size={22} />, tone: "purple" },
        { to: "/admin/intelligence", title: "Security intelligence", text: "Risk, attacks and incidents.", icon: <IconCpu size={22} />, tone: "orange" },
      ]} />
      <div className="row row-cards row-deck">
        <div className="col-lg-8">
          <Card title="Audit activity" subtitle="Events per day, last 14 days (latest 200 loaded).">
            <AsyncView state={audit} onRetry={audit.reload} loadingLabel="Loading audit activity" errorTitle="Audit activity is unavailable">
              {(rows) => rows.length === 0
                ? <EmptyState title="No audit events" />
                : <BarChart ariaLabel="Audit events per day" data={eventsPerDay(rows)} />}
            </AsyncView>
          </Card>
        </div>
        <div className="col-lg-4">
          <Card title="Event mix">
            <AsyncView state={audit} onRetry={audit.reload} loadingLabel="Loading event mix">
              {(rows) => rows.length === 0
                ? <EmptyState title="No audit events" />
                : <DonutChart ariaLabel="Most frequent audit events" centerLabel="events" data={eventMix(rows)} />}
            </AsyncView>
          </Card>
        </div>
      </div>
      <div className="row row-cards row-deck">
        <div className="col-lg-5">
          <Card title="Services" flush>
            <AsyncView state={gateway} onRetry={gateway.reload} loadingLabel="Checking services">
              {(status) => (
                <>
                  <div className="card-body border-bottom">
                    <div className="d-flex flex-wrap gap-3">
                      <span className="d-inline-flex align-items-center gap-2">Gateway <Badge tone={healthTone(status.gatewayStatus)}>{humanize(status.gatewayStatus)}</Badge></span>
                      <span className="d-inline-flex align-items-center gap-2">Overall <Badge tone={healthTone(status.systemHealth)}>{humanize(status.systemHealth)}</Badge></span>
                    </div>
                  </div>
                  <Table caption="Service health">
                    <thead><tr><th scope="col">Service</th><th scope="col">Status</th></tr></thead>
                    <tbody>
                      {Object.entries(status.services).map(([name, value]) => {
                        const tone = healthTone(String(value));
                        return (
                          <tr key={name}>
                            <td data-label="Service"><span className={`status-dot ${DOT[tone]} me-2`} aria-hidden="true" />{humanize(name)}</td>
                            <td data-label="Status"><Badge tone={tone}>{humanize(String(value))}</Badge></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </Table>
                </>
              )}
            </AsyncView>
          </Card>
        </div>
        <div className="col-lg-7">
          <Card title="Persistence">
            <AsyncView state={persistence} onRetry={persistence.reload} loadingLabel="Reading persistence statistics">
              {(stats) => (
                <>
                  <p className="small text-secondary">Authoritative store: <strong className="text-body">{stats.authoritativePersistence}</strong></p>
                  <Grid cols={3}>
                    {Object.entries(stats.counts).map(([key, value]) => <Stat key={key} label={humanize(key)} value={value} />)}
                  </Grid>
                </>
              )}
            </AsyncView>
          </Card>
        </div>
      </div>
    </Page>
  );
};
