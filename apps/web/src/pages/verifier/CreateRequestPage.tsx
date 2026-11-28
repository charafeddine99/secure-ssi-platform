import React from "react";
import { IconRefresh } from "@tabler/icons-react";
import { createOid4vpSession, getOid4vpSession, type Oid4vpSession } from "../../api/presentation.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Checkbox, SelectField, TextAreaField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { QrPanel } from "../../components/ui/QrPanel.tsx";
import { Badge, type BadgeTone } from "../../components/ui/StatusBadge.tsx";
import { PolicyBanner, VerificationMatrix } from "../../components/ssi/VerificationMatrix.tsx";
import { describeError, isApiError } from "../../lib/http.ts";
import { formatDateTime, humanize, renderClaimValue } from "../../lib/format.ts";
import { REQUEST_PROFILES } from "./verifierLogic.ts";

function sessionTone(status: string): BadgeTone {
  if (status === "VERIFIED") return "success";
  if (status === "REJECTED") return "danger";
  if (status === "PENDING") return "info";
  return "neutral";
}

export const CreateRequestPage: React.FC = () => {
  const [type, setType] = React.useState("UniversityAffiliationCredential");
  const [fields, setFields] = React.useState<string[]>([]);
  const [purpose, setPurpose] = React.useState("");
  const [ttl, setTtl] = React.useState("600");
  const [creating, setCreating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [session, setSession] = React.useState<Oid4vpSession | null>(null);
  const [pollError, setPollError] = React.useState<string | null>(null);
  const profile = REQUEST_PROFILES[type];

  const poll = React.useCallback(async (current: Oid4vpSession) => {
    const expiry = Date.parse(current.expiresAt);
    if (Number.isFinite(expiry) && Date.now() >= expiry) {
      setSession((s) => (s?.sessionId === current.sessionId ? { ...s, status: "EXPIRED" } : s));
      return;
    }
    try {
      setSession(await getOid4vpSession(current.sessionId));
      setPollError(null);
    } catch (cause) {
      if (isApiError(cause) && cause.status === 410) {
        setSession((s) => (s?.sessionId === current.sessionId ? { ...s, status: "EXPIRED" } : s));
      } else {
        setPollError(`${describeError(cause)} Retrying automatically.`);
      }
    }
  }, []);

  React.useEffect(() => {
    if (!session || session.status !== "PENDING") return;
    const timer = window.setInterval(() => { void poll(session); }, 2500);
    return () => window.clearInterval(timer);
  }, [session, poll]);

  const onCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (purpose.trim().length < 10) { setError("Describe the purpose in at least 10 characters so the holder can make an informed decision."); return; }
    if (fields.length === 0) { setError("Select at least one field."); return; }
    setCreating(true);
    try {
      setSession(await createOid4vpSession({ purpose: purpose.trim(), requestedCredentialTypes: [type], requestedFields: fields, ttlSeconds: Number(ttl) }));
      setPollError(null);
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setCreating(false);
    }
  };

  const toggle = (id: string) => setFields((current) => (current.includes(id) ? current.filter((f) => f !== id) : [...current, id]));

  return (
    <Page
      eyebrow="Verifier workspace"
      title="New presentation request"
      description="Ask only for what you need."
      breadcrumbs={[{ label: "Verifier", to: "/verifier" }, { label: "New request" }]}
    >
      {!session && (
        <form onSubmit={onCreate} noValidate>
          <Card
            title="Request details"
            footer={<div className="d-flex justify-content-end"><Button type="submit" loading={creating}>Create request</Button></div>}
          >
            <div className="row">
              <div className="col-lg-6">
                <SelectField label="Credential type" value={type} onChange={(e) => { setType(e.target.value); setFields([]); }}>
                  {Object.entries(REQUEST_PROFILES).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}
                </SelectField>
                <fieldset className="mb-3">
                  <legend className="form-label required">Fields to match</legend>
                  {profile.fields.map((field) => (
                    <Checkbox key={field.id} checked={fields.includes(field.id)} onChange={() => toggle(field.id)} label={field.label} />
                  ))}
                  <small className="form-hint">Fields select the credential; the full credential is sent.</small>
                </fieldset>
              </div>
              <div className="col-lg-6">
                <TextAreaField label="Purpose shown to the holder" rows={4} value={purpose} onChange={(e) => setPurpose(e.target.value)} maxLength={300} required />
                <SelectField label="Request lifetime" value={ttl} onChange={(e) => setTtl(e.target.value)}>
                  <option value="300">5 minutes</option>
                  <option value="600">10 minutes</option>
                  <option value="1800">30 minutes</option>
                </SelectField>
              </div>
            </div>
            {error && <Alert tone="danger" live="assertive" title="Request not created">{error}</Alert>}
          </Card>
        </form>
      )}

      {session && (
        <>
          <div className="row row-cards row-deck">
            <div className="col-md-5">
              <Card className="h-100" title="Share with the holder" actions={<Badge tone={sessionTone(session.status)}>{humanize(session.status)}</Badge>}>
                {session.status === "PENDING" ? <><QrPanel value={session.qrPayload || session.deepLinkUri} label="OID4VP presentation request" />{!session.handoffUri && <Alert tone="warning" className="mt-3" title="Not for a phone camera">No public address is configured, so this code holds an openid4vp:// link. A phone camera cannot open it. Paste the link into Receive or share in the wallet.</Alert>}</> : <p className="text-secondary mb-0">This request is closed.</p>}
              </Card>
            </div>
            <div className="col-md-7">
              <Card
                className="h-100"
                title="Request"
                footer={(
                  <div className="btn-list">
                    <Button variant="secondary" size="sm" onClick={() => poll(session)} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>
                    <Button variant="ghost" size="sm" onClick={() => { setSession(null); setPollError(null); }}>New request</Button>
                  </div>
                )}
              >
                <DataGrid items={[
                  { label: "Purpose", value: session.purpose },
                  { label: "Fields", value: session.requestedFields.join(", ") },
                  { label: "Expires", value: formatDateTime(session.expiresAt) },
                  { label: "Holder decision", value: humanize(session.consentStatus || "PENDING") },
                ]} />
                {session.status === "PENDING" && session.deepLinkUri.includes("request_uri=") && (
                  <div className="mt-3">
                    <div className="small fw-semibold mb-1">Link for other OpenID4VP wallets</div>
                    <p className="small text-secondary mb-1">Holds only the verifier key (client_id) and a request_uri. The wallet fetches the signed request from that address.</p>
                    <code className="d-block small text-break" aria-label="openid4vp request link">{session.deepLinkUri}</code>
                  </div>
                )}
                {pollError && <Alert tone="warning" title="Status refresh failed" className="mt-3">{pollError}</Alert>}
              </Card>
            </div>
          </div>
          <PolicyBanner
            result={session.verificationResult}
            pendingText={session.status === "REJECTED" && !session.verificationResult
              ? `The holder declined${session.rejectionReason ? `: ${session.rejectionReason}` : "."}`
              : session.status === "EXPIRED" ? "The request expired before a presentation arrived." : undefined}
          />
          {session.verificationResult && <Card title="Verification checks" flush><VerificationMatrix result={session.verificationResult} /></Card>}
          {session.disclosedClaims && Object.keys(session.disclosedClaims).length > 0 && (
            <Card title="Disclosed attributes" flush>
              <Table caption="Disclosed attributes">
                <thead><tr><th scope="col">Attribute</th><th scope="col">Value</th></tr></thead>
                <tbody>{Object.entries(session.disclosedClaims).map(([k, v]) => <tr key={k}><th scope="row" className="fw-medium">{humanize(k)}</th><td data-label="Value">{renderClaimValue(v)}</td></tr>)}</tbody>
              </Table>
            </Card>
          )}
        </>
      )}
    </Page>
  );
};
