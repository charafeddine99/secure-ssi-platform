import React, { useCallback, useEffect, useState } from "react";
import { Building2, RefreshCw, Save, ShieldCheck, Users } from "lucide-react";
import {
  AdminIssuerScopeOption,
  AdminUserRecord,
  fetchAdminIssuerScopeOptions,
  fetchAdminUsers,
  updateAdminIssuerScope,
} from "../../services/api";

export const AdminUsersPage: React.FC = () => {
  const [users, setUsers] = useState<AdminUserRecord[]>([]);
  const [issuerOptions, setIssuerOptions] = useState<AdminIssuerScopeOption[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [records, options] = await Promise.all([
        fetchAdminUsers(),
        fetchAdminIssuerScopeOptions(),
      ]);
      setUsers(records);
      setIssuerOptions(options);
      setDrafts(Object.fromEntries(records.map((record) => [record.id, record.issuerDid || ""])));
    } catch (error) {
      setUsers([]);
      setIssuerOptions([]);
      setLoadError(error instanceof Error ? error.message : "The user directory is unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const saveScope = async (record: AdminUserRecord) => {
    const selectedIssuerDid = drafts[record.id] ?? record.issuerDid ?? "";
    setSavingId(record.id);
    setActionNotice(null);
    setLoadError(null);
    try {
      const updated = await updateAdminIssuerScope(
        record.id,
        selectedIssuerDid || null,
        record.version,
      );
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      setDrafts((current) => ({ ...current, [updated.id]: updated.issuerDid || "" }));
      setActionNotice(`Institution access updated for ${updated.username}.`);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "The institution assignment failed.");
    } finally {
      setSavingId(null);
    }
  };

  const issuerCount = users.filter((record) => record.roles.includes("issuer")).length;
  const assignedCount = users.filter((record) => record.roles.includes("issuer") && record.issuerDid).length;

  return (
    <div className="workspace-page">
      <header className="workspace-page-header">
        <div>
          <p className="workspace-eyebrow">Administration · Identity access</p>
          <h1>Users and institutions</h1>
          <p>Connect existing Issuer accounts to an active trusted institution with a configured signing key.</p>
        </div>
        <div className="workspace-header-actions">
          <button className="workspace-secondary-action" type="button" onClick={() => void loadData()} disabled={loading}>
            <RefreshCw size={16} aria-hidden="true" />
            Refresh directory
          </button>
        </div>
      </header>

      <section className="workspace-metrics" aria-label="Identity directory summary">
        <article className="workspace-metric-card">
          <span>Accounts shown</span>
          <strong>{loading ? "Loading" : users.length}</strong>
          <small>Persistent accounts returned by Identity Service</small>
        </article>
        <article className="workspace-metric-card">
          <span>Issuer accounts</span>
          <strong>{loading ? "Loading" : issuerCount}</strong>
          <small>Issuer role confirmed by the server</small>
        </article>
        <article className="workspace-metric-card">
          <span>Institution assigned</span>
          <strong>{loading ? "Loading" : assignedCount}</strong>
          <small>Issuer accounts with a server-side DID binding</small>
        </article>
      </section>

      <section className="workspace-panel" aria-labelledby="admin-users-title">
        <div className="workspace-panel-header">
          <div>
            <h2 id="admin-users-title">Persistent accounts</h2>
            <p>Only user identity, role, account state, and institution scope are shown. Password material is never returned.</p>
          </div>
        </div>

        <div className="workspace-inline-note" role="note">
          <ShieldCheck size={17} aria-hidden="true" />
          <span>Scope changes apply only to existing Issuer accounts. Available institutions must be active in the Trust Registry and have a configured signing key. Synthetic fixture accounts cannot be edited here.</span>
        </div>

        {loadError && <div className="workspace-inline-error" role="alert">{loadError}</div>}
        {actionNotice && <div className="workspace-inline-success" role="status">{actionNotice}</div>}

        <div className="workspace-table-wrap">
          <table className="workspace-table admin-users-table">
            <thead>
              <tr>
                <th scope="col">Account</th>
                <th scope="col">Role</th>
                <th scope="col">Account state</th>
                <th scope="col">Institution access</th>
                <th scope="col"><span className="sr-only">Save changes</span></th>
              </tr>
            </thead>
            <tbody>
              {users.map((record) => {
                const isIssuer = record.roles.includes("issuer");
                const selectedDid = drafts[record.id] ?? record.issuerDid ?? "";
                const unchanged = selectedDid === (record.issuerDid || "");
                return (
                  <tr key={record.id}>
                    <td>
                      <strong>{record.displayName}</strong>
                      <span className="workspace-cell-secondary">{record.username}</span>
                    </td>
                    <td>{record.roles.map((role) => role.replace(/_/g, " ")).join(", ")}</td>
                    <td><span className={`workspace-status ${record.enabled ? "is-active" : "is-inactive"}`}>{record.enabled ? "Enabled" : "Disabled"}</span></td>
                    <td>
                      {isIssuer ? (
                        <select
                          aria-label={`Institution access for ${record.username}`}
                          className="workspace-select"
                          value={selectedDid}
                          onChange={(event) => setDrafts((current) => ({ ...current, [record.id]: event.target.value }))}
                          disabled={loading || savingId === record.id}
                        >
                          <option value="">No institution assigned</option>
                          {issuerOptions.map((option) => (
                            <option key={option.issuerDid} value={option.issuerDid}>
                              {option.organizationName} · {option.issuerDid}
                            </option>
                          ))}
                          {record.issuerDid && !issuerOptions.some((option) => option.issuerDid === record.issuerDid) && (
                            <option value={record.issuerDid}>{record.issuerOrganizationName || "Current institution"} · {record.issuerDid}</option>
                          )}
                        </select>
                      ) : (
                        <span className="workspace-cell-secondary">Not applicable</span>
                      )}
                    </td>
                    <td className="workspace-table-action-cell">
                      {isIssuer && (
                        <button
                          className="workspace-secondary-action workspace-table-action"
                          type="button"
                          onClick={() => void saveScope(record)}
                          disabled={loading || savingId === record.id || unchanged}
                          aria-label={`Save institution access for ${record.username}`}
                        >
                          {savingId === record.id ? <RefreshCw size={15} className="spin" aria-hidden="true" /> : <Save size={15} aria-hidden="true" />}
                          <span>{savingId === record.id ? "Saving" : "Save"}</span>
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!loading && users.length === 0 && (
                <tr>
                  <td colSpan={5}>
                    <div className="workspace-empty-state">
                      <Users size={20} aria-hidden="true" />
                      <strong>{loadError ? "User directory unavailable" : "No persistent accounts found"}</strong>
                      <span>{loadError ? "Check the configured Identity Service provider and try again." : "There are no persisted users to manage."}</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {issuerOptions.length === 0 && !loading && !loadError && (
          <p className="workspace-footnote"><Building2 size={14} aria-hidden="true" /> No active trusted issuer with a configured signing key is currently available.</p>
        )}
      </section>
    </div>
  );
};
