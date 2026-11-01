import React from "react";
import { IconCertificate, IconDeviceFloppy, IconRefresh, IconUsers, IconUserShield } from "@tabler/icons-react";
import { fetchAdminIssuerScopeOptions, fetchAdminUsers, updateAdminIssuerScope, type AdminIssuerScopeOption, type AdminUserRecord } from "../../api/admin.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, Stat, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useToast } from "../../components/ui/toastContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { ApiError, describeError, isApiError } from "../../lib/http.ts";

interface Directory { users: AdminUserRecord[]; options: AdminIssuerScopeOption[] }

export const AdminUsersPage: React.FC = () => {
  const toast = useToast();
  const data = useAsync<Directory>(async () => {
    try {
      const [users, options] = await Promise.all([fetchAdminUsers(), fetchAdminIssuerScopeOptions()]);
      return { users, options };
    } catch (error) {
      // Identity Service answers 503 while it runs on the read-only sample account set.
      if (isApiError(error) && error.status === 503) {
        throw new ApiError("unavailable", "User administration needs the persistent account store. The built-in sample accounts are read-only.", 503, error.code);
      }
      throw error;
    }
  }, []);
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});
  const [saving, setSaving] = React.useState<string | null>(null);
  const [overrides, setOverrides] = React.useState<Record<string, AdminUserRecord>>({});

  const save = async (record: AdminUserRecord) => {
    const selected = drafts[record.id] ?? record.issuerDid ?? "";
    setSaving(record.id);
    try {
      const updated = await updateAdminIssuerScope(record.id, selected || null, record.version);
      setOverrides((current) => ({ ...current, [updated.id]: updated }));
      toast("success", `Institution access updated for ${updated.username}.`);
    } catch (error) {
      toast("danger", describeError(error));
    } finally {
      setSaving(null);
    }
  };

  return (
    <Page
        eyebrow="Administration"
        title="Users and issuer scope"
        description="Link issuer accounts to a trusted institution."
        breadcrumbs={[{ label: "Administration", to: "/admin" }, { label: "Users" }]}
        actions={<Button variant="secondary" onClick={data.reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
    >
      <AsyncView state={data} onRetry={data.reload} loadingLabel="Loading user directory" errorTitle="The user directory is unavailable">
        {({ users: base, options }) => {
          const users = base.map((u) => overrides[u.id] ?? u);
          const issuers = users.filter((u) => u.roles.includes("issuer"));
          return (
            <>
              <Grid cols={3}>
                <Stat label="Accounts" value={users.length} icon={<IconUsers size={20} />} />
                <Stat label="Issuer accounts" value={issuers.length} icon={<IconCertificate size={20} />} tone="indigo" />
                <Stat label="Issuers with institution" value={issuers.filter((u) => u.issuerDid).length} icon={<IconUserShield size={20} />} tone="teal" />
              </Grid>
              <Card title="Accounts" flush>
                {users.length === 0 ? <EmptyState title="No accounts" description="The identity store returned no accounts." /> : (
                  <Table caption="Platform accounts" stackBelow="md">
                    <thead><tr><th scope="col">Account</th><th scope="col">Roles</th><th scope="col">State</th><th scope="col">Issuing institution</th></tr></thead>
                    <tbody>
                      {users.map((record) => {
                        const isIssuer = record.roles.includes("issuer");
                        const draft = drafts[record.id] ?? record.issuerDid ?? "";
                        const selectId = `scope-${record.id}`;
                        return (
                          <tr key={record.id}>
                            <td data-label="Account"><div className="fw-medium">{record.displayName}</div><div className="small text-secondary">{record.username}</div></td>
                            <td data-label="Roles"><div className="d-flex flex-wrap gap-1">{record.roles.map((r) => <Badge key={r} tone="brand">{r}</Badge>)}</div></td>
                            <td data-label="State">{record.enabled ? <Badge tone="success">Enabled</Badge> : <Badge tone="neutral">Disabled</Badge>}</td>
                            <td data-label="Issuing institution">
                              {!isIssuer ? <span className="text-secondary">Not applicable</span> : (
                                <div className="d-flex flex-wrap gap-2 align-items-center">
                                  <div className="flex-fill" style={{ minWidth: "12rem" }}>
                                    <label className="visually-hidden" htmlFor={selectId}>Institution for {record.username}</label>
                                    <select id={selectId} className="form-select form-select-sm" value={draft} onChange={(e) => setDrafts((c) => ({ ...c, [record.id]: e.target.value }))}>
                                      <option value="">No institution</option>
                                      {options.map((o) => <option key={o.issuerDid} value={o.issuerDid}>{o.organizationName}</option>)}
                                    </select>
                                  </div>
                                  <Button size="sm" variant="secondary" onClick={() => save(record)} loading={saving === record.id} disabled={draft === (record.issuerDid ?? "")} icon={<IconDeviceFloppy aria-hidden="true" />}>
                                    Save<span className="visually-hidden"> for {record.username}</span>
                                  </Button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </Table>
                )}
              </Card>
            </>
          );
        }}
      </AsyncView>
    </Page>
  );
};
