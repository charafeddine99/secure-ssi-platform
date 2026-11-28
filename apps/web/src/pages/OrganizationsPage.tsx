import React from "react";
import { IconBuilding, IconMailForward, IconUserPlus } from "@tabler/icons-react";
import {
  acceptInvitation,
  applyForOrganization,
  inviteMember,
  listCapabilities,
  listInvitations,
  listMembers,
  listMyOrganizations,
  ORG_ROLES,
  ORGANIZATION_TYPES,
  removeMember,
  requestCapability,
  revokeInvitation,
  type Membership,
  type Organization,
  type OrganizationType,
  type OrgRole,
} from "../api/organizations.ts";
import { Page } from "../components/ui/PageHeader.tsx";
import { Card } from "../components/ui/Card.tsx";
import { Button } from "../components/ui/Button.tsx";
import { Checkbox, SelectField, TextAreaField, TextField } from "../components/ui/Field.tsx";
import { Alert } from "../components/ui/Alert.tsx";
import { Badge } from "../components/ui/StatusBadge.tsx";
import { ErrorState, LoadingState } from "../components/ui/States.tsx";
import { useAsync } from "../lib/useAsync.ts";
import { describeError } from "../lib/http.ts";

const STATUS_TONE = { ACTIVE: "success", SUBMITTED: "warning", PENDING: "warning", REJECTED: "danger", SUSPENDED: "danger", REVOKED: "danger", REMOVED: "neutral" } as const;

/** Your organizations, applying for one, and accepting an invitation. Every action is re-checked by the server. */
export const OrganizationsPage: React.FC = () => {
  const mine = useAsync(() => listMyOrganizations(), []);
  const [selected, setSelected] = React.useState<string | null>(null);
  React.useEffect(() => { document.title = "Organizations · Secure SSI Platform"; }, []);
  const current = mine.status === "success" ? mine.data.find((item) => item.organization.organizationId === selected) : undefined;

  return (
    <Page eyebrow="Account" title="Organizations" description="Your memberships, applications and invitations. Your personal wallet stays yours in every organization.">
      <Card title="Your organizations" subtitle="Roles apply only inside the organization that gave them.">
        {mine.status === "loading" && <LoadingState label="Loading organizations" rows={2} />}
        {mine.status === "error" && <ErrorState error={mine.error} title="Organizations are unavailable" onRetry={mine.reload} />}
        {mine.status === "success" && (mine.data.length === 0 ? (
          <p className="mb-0">You are not a member of any organization yet.</p>
        ) : (
          <ul className="list-group list-group-flush" aria-label="Your organizations">
            {mine.data.map(({ organization, membership }) => (
              <li key={organization.organizationId} className="list-group-item px-0 d-flex flex-wrap gap-2 align-items-center">
                <div className="me-auto">
                  <div className="fw-bold">{organization.legalName}</div>
                  <div className="text-secondary small">{organization.organizationType} · {membership.roles.join(", ")}</div>
                </div>
                <Badge tone={STATUS_TONE[organization.status]}>{organization.status}</Badge>
                {membership.status === "ACTIVE" && organization.status !== "REVOKED" && (
                  <Button size="sm" variant="secondary" onClick={() => setSelected(organization.organizationId)}>Open</Button>
                )}
              </li>
            ))}
          </ul>
        ))}
      </Card>
      {current && <OrganizationWorkspace organization={current.organization} membership={current.membership} onChanged={mine.reload} />}
      <AcceptInvitationCard onJoined={mine.reload} />
      <ApplicationCard onSubmitted={mine.reload} />
    </Page>
  );
};

const AcceptInvitationCard: React.FC<{ onJoined: () => void }> = ({ onJoined }) => {
  const [code, setCode] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await acceptInvitation(code);
      setMessage({ tone: "success", text: "You joined the organization." });
      setCode("");
      onJoined();
    } catch (cause) {
      setMessage({ tone: "danger", text: describeError(cause) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="Accept an invitation" subtitle="Invitations work once, for 72 hours, and only for the address they were sent to.">
      <form onSubmit={submit} noValidate aria-label="Accept an organization invitation">
        <TextField label="Invitation code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" required />
        {message && <Alert tone={message.tone} live="polite" title={message.tone === "success" ? "Joined" : "Not accepted"} className="mb-3">{message.text}</Alert>}
        <Button type="submit" variant="secondary" loading={busy} disabled={code.trim().length < 20} icon={<IconMailForward aria-hidden="true" />}>Accept invitation</Button>
      </form>
    </Card>
  );
};

const ApplicationCard: React.FC<{ onSubmitted: () => void }> = ({ onSubmitted }) => {
  const [form, setForm] = React.useState({ legalName: "", organizationType: "UNIVERSITY" as OrganizationType, jurisdiction: "TR", registrationReference: "", officialDomain: "", website: "", officialContact: "", applicantTitle: "", authorityEvidence: "", intendedUse: "" });
  const [caps, setCaps] = React.useState<("ISSUER" | "VERIFIER")[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: e.target.value });
  const toggle = (cap: "ISSUER" | "VERIFIER") => setCaps(caps.includes(cap) ? caps.filter((c) => c !== cap) : [...caps, cap]);
  const ready = form.legalName.trim().length > 1 && form.officialContact.trim().length > 1 && form.applicantTitle.trim().length > 1 && form.authorityEvidence.trim().length > 1 && form.intendedUse.trim().length > 1;
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await applyForOrganization({ ...form, requestedCapabilities: caps });
      setMessage({ tone: "success", text: "Application submitted. A platform reviewer checks that the organization exists and that you may act for it; nothing is active before that." });
      onSubmitted();
    } catch (cause) {
      setMessage({ tone: "danger", text: describeError(cause) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="Apply for an organization" subtitle="For a university, company, public body or other institution. A verified organization still applies separately to issue or verify credentials.">
      <form onSubmit={submit} noValidate aria-label="Organization application">
        <TextField label="Legal name of the organization" value={form.legalName} onChange={set("legalName")} maxLength={300} required />
        <SelectField label="Organization type" value={form.organizationType} onChange={set("organizationType")}>
          {ORGANIZATION_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ").toLowerCase()}</option>)}
        </SelectField>
        <TextField label="Country or jurisdiction" value={form.jurisdiction} onChange={set("jurisdiction")} maxLength={100} required />
        <TextField label="Official registry reference (optional)" hint="For example a MERSİS number for a company, a DETSİS number for a public body, or the official university list." value={form.registrationReference} onChange={set("registrationReference")} maxLength={200} />
        <TextField label="Official domain (optional)" value={form.officialDomain} onChange={set("officialDomain")} maxLength={253} />
        <TextField label="Official website (optional)" value={form.website} onChange={set("website")} maxLength={500} />
        <TextField label="Official contact channel" hint="How a reviewer can confirm with the organization itself, not with you." value={form.officialContact} onChange={set("officialContact")} maxLength={500} required />
        <TextField label="Your role in the organization" value={form.applicantTitle} onChange={set("applicantTitle")} maxLength={500} required />
        <TextAreaField label="Evidence that you may act for it" hint="For example an authorization letter, an e-signed document, or the page of the official site naming you. Describe it; the reviewer verifies it." value={form.authorityEvidence} onChange={set("authorityEvidence")} maxLength={500} required />
        <TextAreaField label="Intended use" value={form.intendedUse} onChange={set("intendedUse")} maxLength={500} required />
        <div className="mb-3">
          <Checkbox label="We intend to issue credentials (issuer capability, reviewed separately)" checked={caps.includes("ISSUER")} onChange={() => toggle("ISSUER")} />
          <Checkbox label="We intend to verify credentials (verifier capability, reviewed separately)" checked={caps.includes("VERIFIER")} onChange={() => toggle("VERIFIER")} />
        </div>
        {message && <Alert tone={message.tone} live="polite" title={message.tone === "success" ? "Submitted" : "Not submitted"} className="mb-3">{message.text}</Alert>}
        <Button type="submit" loading={busy} disabled={!ready} icon={<IconBuilding aria-hidden="true" />}>Submit application</Button>
      </form>
    </Card>
  );
};

const OrganizationWorkspace: React.FC<{ organization: Organization; membership: Membership; onChanged: () => void }> = ({ organization, membership, onChanged }) => {
  const isAdmin = membership.roles.includes("ORG_ADMIN");
  const orgId = organization.organizationId;
  const members = useAsync(() => listMembers(orgId), [orgId]);
  const capabilities = useAsync(() => listCapabilities(orgId), [orgId]);
  const invitations = useAsync(() => (isAdmin ? listInvitations(orgId) : Promise.resolve([])), [orgId, isAdmin]);
  const [email, setEmail] = React.useState("");
  const [roles, setRoles] = React.useState<OrgRole[]>(["ORG_AUDITOR"]);
  const [code, setCode] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [cap, setCap] = React.useState({ type: "ISSUER" as "ISSUER" | "VERIFIER", credentialTypes: "", purpose: "", clientId: "", redirectUris: "" });
  const active = organization.status === "ACTIVE";

  const run = async (operation: () => Promise<unknown>, after?: () => void) => {
    setError(null);
    try {
      await operation();
      after?.();
    } catch (cause) {
      setError(describeError(cause));
    }
  };

  return (
    <Card title={organization.legalName} subtitle={`${organization.organizationType} · your roles: ${membership.roles.join(", ")}`} actions={<Badge tone={STATUS_TONE[organization.status]}>{organization.status}</Badge>}>
      {!active && <Alert tone="warning" live="polite" title="Read only" className="mb-3">This organization is {organization.status.toLowerCase()}: you can read it, but nothing can be changed or issued.</Alert>}
      {error && <Alert tone="danger" live="assertive" title="Not done" className="mb-3">{error}</Alert>}
      <h3 className="h4">Members</h3>
      {members.status === "success" && (
        <ul className="list-group list-group-flush mb-3" aria-label="Members">
          {members.data.map((member) => (
            <li key={member.membershipId} className="list-group-item px-0 d-flex gap-2 align-items-center">
              <span className="me-auto"><code>{member.userId}</code> · {member.roles.join(", ")}</span>
              {isAdmin && active && member.membershipId !== membership.membershipId && (
                <Button size="sm" variant="ghost" onClick={() => run(() => removeMember(orgId, member.membershipId), () => { members.reload(); onChanged(); })}>Remove</Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {isAdmin && active && (
        <form onSubmit={(e) => { e.preventDefault(); void run(async () => { const made = await inviteMember(orgId, email, roles); setCode(made.invitationCode); setEmail(""); invitations.reload(); }); }} noValidate aria-label="Invite a member" className="mb-3">
          <TextField label="Invite by e-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <div className="mb-2">
            {ORG_ROLES.map((role) => (
              <Checkbox key={role} label={role} checked={roles.includes(role)} onChange={() => setRoles(roles.includes(role) ? roles.filter((r) => r !== role) : [...roles, role])} />
            ))}
          </div>
          <Button type="submit" size="sm" variant="secondary" disabled={!email.includes("@") || roles.length === 0} icon={<IconUserPlus aria-hidden="true" />}>Create invitation</Button>
        </form>
      )}
      {code && <Alert tone="info" live="polite" title="Invitation code (shown once)" className="mb-3"><code data-testid="invitation-code">{code}</code><div className="small">Send it to the person yourself; it works once, for 72 hours, and only for that address.</div></Alert>}
      {isAdmin && invitations.status === "success" && invitations.data.length > 0 && (
        <ul className="list-group list-group-flush mb-3" aria-label="Invitations">
          {invitations.data.map((inv) => (
            <li key={inv.invitationId} className="list-group-item px-0 d-flex gap-2 align-items-center">
              <span className="me-auto">{inv.email} · {inv.roles.join(", ")} · {inv.status}</span>
              {inv.status === "OPEN" && <Button size="sm" variant="ghost" onClick={() => run(() => revokeInvitation(orgId, inv.invitationId), invitations.reload)}>Revoke</Button>}
            </li>
          ))}
        </ul>
      )}
      <h3 className="h4">Capabilities</h3>
      {capabilities.status === "success" && (capabilities.data.length === 0 ? <p>No issuer or verifier capability yet.</p> : (
        <ul className="list-group list-group-flush mb-3" aria-label="Capabilities">
          {capabilities.data.map((c) => <li key={c.capabilityId} className="list-group-item px-0">{c.type} · {c.credentialTypes.join(", ")} · <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge></li>)}
        </ul>
      ))}
      {isAdmin && active && (
        <form onSubmit={(e) => { e.preventDefault(); void run(() => requestCapability(orgId, { type: cap.type, credentialTypes: cap.credentialTypes.split(",").map((s) => s.trim()).filter(Boolean), purpose: cap.purpose, ...(cap.type === "VERIFIER" ? { clientId: cap.clientId, redirectUris: cap.redirectUris.split(/\s+/).filter(Boolean) } : {}) }), capabilities.reload); }} noValidate aria-label="Request a capability">
          <SelectField label="Capability" value={cap.type} onChange={(e) => setCap({ ...cap, type: e.target.value as "ISSUER" | "VERIFIER" })}>
            <option value="ISSUER">Issuer</option>
            <option value="VERIFIER">Verifier</option>
          </SelectField>
          <TextField label="Credential types (comma separated)" value={cap.credentialTypes} onChange={(e) => setCap({ ...cap, credentialTypes: e.target.value })} required />
          <TextAreaField label="Purpose" value={cap.purpose} onChange={(e) => setCap({ ...cap, purpose: e.target.value })} maxLength={500} required />
          {cap.type === "VERIFIER" && (
            <>
              <TextField label="Client identifier" value={cap.clientId} onChange={(e) => setCap({ ...cap, clientId: e.target.value })} required />
              <TextAreaField label="Exact redirect URIs (one per line)" hint="Exact HTTPS URIs; no wildcards or fragments." value={cap.redirectUris} onChange={(e) => setCap({ ...cap, redirectUris: e.target.value })} required />
            </>
          )}
          <Button type="submit" size="sm" variant="secondary" disabled={!cap.credentialTypes.trim() || cap.purpose.trim().length < 2}>Request capability</Button>
        </form>
      )}
    </Card>
  );
};
