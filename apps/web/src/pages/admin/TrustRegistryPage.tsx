import React from "react";
import { IconPlus, IconRefresh } from "@tabler/icons-react";
import { changeTrustStatus, fetchPublicTrustedIssuers, registerTrustedIssuer, type TrustRecord } from "../../api/admin.ts";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { TextAreaField, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { ConfirmDialog } from "../../components/ui/Dialog.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { Badge, type BadgeTone } from "../../components/ui/StatusBadge.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useToast } from "../../components/ui/toastContext.ts";
import { useAuth } from "../../context/AuthContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDate, humanize } from "../../lib/format.ts";

function trustTone(status: string): BadgeTone {
  const s = status.toUpperCase();
  if (s === "ACTIVE" || s === "TRUSTED") return "success";
  if (s === "SUSPENDED") return "warning";
  if (s === "REVOKED") return "danger";
  return "neutral";
}

export const TrustRegistryPage: React.FC = () => {
  const toast = useToast();
  const withStepUp = useStepUp();
  const { hasPermission } = useAuth();
  const canManage = hasPermission("trust-registry:write");
  const records = useAsync((signal) => fetchPublicTrustedIssuers(signal), []);
  const [did, setDid] = React.useState("");
  const [org, setOrg] = React.useState("");
  const [types, setTypes] = React.useState("UniversityAffiliationCredential");
  const [days, setDays] = React.useState("365");
  const [adding, setAdding] = React.useState(false);
  const [addError, setAddError] = React.useState<string | null>(null);
  const [action, setAction] = React.useState<{ record: TrustRecord; kind: "suspend" | "revoke" } | null>(null);
  const [reason, setReason] = React.useState("");
  const [acting, setActing] = React.useState(false);

  const onRegister = async (event: React.FormEvent) => {
    event.preventDefault();
    setAddError(null);
    const typeList = types.split(",").map((t) => t.trim()).filter(Boolean);
    const validDays = Number(days);
    if (!did.trim().startsWith("did:")) { setAddError("The issuer DID must start with did:."); return; }
    if (org.trim().length < 2) { setAddError("Enter the organisation name."); return; }
    if (typeList.length === 0) { setAddError("List at least one permitted credential type."); return; }
    if (!Number.isInteger(validDays) || validDays < 1 || validDays > 3650) { setAddError("Validity must be 1 to 3650 days."); return; }
    setAdding(true);
    try {
      await withStepUp("trust.registry.write", did.trim(), (token) => registerTrustedIssuer({ issuerDid: did.trim(), organizationName: org.trim(), permittedCredentialTypes: typeList, validDays }, token));
      setDid(""); setOrg("");
      toast("success", "Issuer added to the trust registry.");
      records.reload();
    } catch (error) {
      setAddError(describeError(error));
    } finally {
      setAdding(false);
    }
  };

  const onAction = async () => {
    if (!action) return;
    setActing(true);
    try {
      await withStepUp("trust.registry.write", action.record.id, (token) => changeTrustStatus(action.record.id, action.kind, reason.trim(), token));
      toast("success", action.kind === "revoke" ? "Issuer revoked." : "Issuer suspended.");
      setAction(null);
      setReason("");
      records.reload();
    } catch (error) {
      toast("danger", describeError(error));
    } finally {
      setActing(false);
    }
  };

  return (
    <Page
        eyebrow="Administration"
        title="Trust registry"
        description="Issuers that verifiers accept."
        breadcrumbs={[{ label: "Administration", to: "/admin" }, { label: "Trust registry" }]}
        actions={<Button variant="secondary" onClick={records.reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
    >
      <Card title="Registered issuers" flush>
        <AsyncView state={records} onRetry={records.reload} loadingLabel="Loading trust registry">
          {(items) => items.length === 0 ? <EmptyState title="No trusted issuers" description="No issuer is currently trusted, so every credential fails the issuer-trust check." /> : (
            <Table caption="Trusted issuers" stackBelow="md">
              <thead><tr><th scope="col">Organisation</th><th scope="col">Issuer DID</th><th scope="col">Credential types</th><th scope="col">Status</th><th scope="col">Valid</th>{canManage && <th scope="col"><span className="visually-hidden">Actions</span></th>}</tr></thead>
              <tbody>
                {items.map((record) => (
                  <tr key={record.id}>
                    <td data-label="Organisation" className="fw-medium">{record.organizationName}</td>
                    <td data-label="Issuer DID"><IdentifierText value={record.issuerDid} label="issuer DID" /></td>
                    <td data-label="Credential types">{record.permittedCredentialTypes.map(humanize).join(", ")}</td>
                    <td data-label="Status"><Badge tone={trustTone(record.trustStatus)}>{humanize(record.trustStatus)}</Badge></td>
                    <td data-label="Valid" className="text-secondary small"><span className="d-block text-nowrap">{formatDate(record.validFrom)}</span><span className="d-block text-nowrap">to {record.validUntil ? formatDate(record.validUntil) : "open"}</span></td>
                    {canManage && (
                      <td data-label="Actions" className="text-end">
                        {record.trustStatus.toUpperCase() !== "REVOKED" && (
                          <div className="btn-list flex-nowrap justify-content-end">
                            {record.trustStatus.toUpperCase() !== "SUSPENDED" && <Button size="sm" variant="secondary" onClick={() => setAction({ record, kind: "suspend" })}>Suspend<span className="visually-hidden"> {record.organizationName}</span></Button>}
                            <Button size="sm" variant="danger" onClick={() => setAction({ record, kind: "revoke" })}>Revoke<span className="visually-hidden"> {record.organizationName}</span></Button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </AsyncView>
      </Card>

      {canManage ? (
        <form onSubmit={onRegister} noValidate>
          <Card
            title="Register an issuer"
            footer={<div className="d-flex justify-content-end"><Button type="submit" loading={adding} icon={<IconPlus aria-hidden="true" />}>Register issuer</Button></div>}
          >
            <div className="row">
              <TextField groupClassName="col-md-6 mb-3" className="font-monospace" label="Issuer DID" value={did} onChange={(e) => setDid(e.target.value)} spellCheck={false} autoComplete="off" required />
              <TextField groupClassName="col-md-6 mb-3" label="Organisation name" value={org} onChange={(e) => setOrg(e.target.value)} required />
              <TextField groupClassName="col-md-8 mb-3" label="Permitted credential types" hint="Comma-separated configuration IDs." value={types} onChange={(e) => setTypes(e.target.value)} required />
              <TextField groupClassName="col-md-4 mb-3" label="Valid for (days)" type="number" min={1} max={3650} value={days} onChange={(e) => setDays(e.target.value)} required />
            </div>
            {addError && <Alert tone="danger" live="assertive" title="Issuer not registered">{addError}</Alert>}
          </Card>
        </form>
      ) : (
        <Alert tone="info">View only: changing the registry requires trust-registry:write.</Alert>
      )}

      <ConfirmDialog
        open={action !== null}
        title={action?.kind === "revoke" ? "Revoke this issuer?" : "Suspend this issuer?"}
        confirmLabel={action?.kind === "revoke" ? "Revoke issuer" : "Suspend issuer"}
        confirmVariant="danger"
        busy={acting}
        onConfirm={onAction}
        onCancel={() => { setAction(null); setReason(""); }}
      >
        <p>{action?.kind === "revoke" ? "Revocation is permanent. " : ""}Credentials from {action?.record.organizationName} will fail the issuer-trust check.</p>
        <TextAreaField label="Reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} required />
      </ConfirmDialog>
    </Page>
  );
};
