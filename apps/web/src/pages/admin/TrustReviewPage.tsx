import React from "react";
import { capabilityQueue, decideCapability, decideOrganization, reviewQueue, TRUST_REVIEW_ACTION, type ReviewItem } from "../../api/organizations.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Checkbox, TextAreaField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";

/**
 * Platform trust review. Two separate checks before approval: the organization exists (official registry
 * or founding law), and the applicant may act for it. The server refuses reviewers who belong to or
 * applied for the organization, so nobody approves their own organization or capability.
 */
export const TrustReviewPage: React.FC = () => {
  const organizations = useAsync(() => reviewQueue("SUBMITTED"), []);
  const capabilities = useAsync(() => capabilityQueue("PENDING"), []);
  React.useEffect(() => { document.title = "Trust review · Secure SSI Platform"; }, []);
  return (
    <Page eyebrow="Platform" title="Trust review" description="Organization applications and issuer/verifier capability requests. Each decision is audited.">
      <Card title="Organization applications">
        {organizations.status === "loading" && <LoadingState label="Loading applications" rows={2} />}
        {organizations.status === "error" && <ErrorState error={organizations.error} title="Applications are unavailable" onRetry={organizations.reload} />}
        {organizations.status === "success" && (organizations.data.length === 0 ? <p className="mb-0">No applications are waiting.</p> : (
          organizations.data.map((item) => <OrganizationDecision key={item.organization.organizationId} item={item} onDone={organizations.reload} />)
        ))}
      </Card>
      <Card title="Capability requests">
        {capabilities.status === "success" && (capabilities.data.length === 0 ? <p className="mb-0">No capability requests are waiting.</p> : (
          capabilities.data.map((cap) => <CapabilityDecision key={cap.capabilityId} id={cap.capabilityId} summary={`${cap.type} for ${cap.organizationId}: ${cap.credentialTypes.join(", ")}${cap.redirectUris ? ` · redirect ${cap.redirectUris.join(" ")}` : ""} · ${cap.purpose}`} onDone={capabilities.reload} />)
        ))}
        {capabilities.status === "error" && <ErrorState error={capabilities.error} title="Capability requests are unavailable" onRetry={capabilities.reload} />}
      </Card>
    </Page>
  );
};

const OrganizationDecision: React.FC<{ item: ReviewItem; onDone: () => void }> = ({ item, onDone }) => {
  const withStepUp = useStepUp();
  const org = item.organization;
  const [entity, setEntity] = React.useState(false);
  const [entityEvidence, setEntityEvidence] = React.useState("");
  const [representative, setRepresentative] = React.useState(false);
  const [representativeEvidence, setRepresentativeEvidence] = React.useState("");
  const [note, setNote] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const decide = async (decision: "APPROVE" | "REJECT") => {
    setError(null);
    try {
      await withStepUp(TRUST_REVIEW_ACTION, org.organizationId, (token) => decideOrganization(org.organizationId, { decision, entityVerified: entity, entityEvidence, representativeVerified: representative, representativeEvidence, note }, token));
      onDone();
    } catch (cause) {
      setError(describeError(cause));
    }
  };
  return (
    <section className="border rounded p-3 mb-3" aria-label={`Application from ${org.legalName}`}>
      <h3 className="h4 mb-1">{org.legalName}</h3>
      <p className="text-secondary small mb-2">{org.organizationType} · {org.jurisdiction} · registry: {org.registrationReference ?? "not given"} · domain: {org.officialDomain ?? "not given"} · capabilities asked: {org.requestedCapabilities.join(", ") || "none"}</p>
      <p className="small mb-1"><strong>Applicant</strong> {item.applicantTitle} (<code>{item.applicantUserId}</code>) · evidence: {item.authorityEvidence}</p>
      <p className="small mb-2"><strong>Official contact</strong> {item.officialContact} · <strong>Use</strong> {item.intendedUse}</p>
      <Checkbox label="The organization exists (checked in an official registry or founding law)" checked={entity} onChange={() => setEntity(!entity)} />
      <TextAreaField label="How the organization was verified" value={entityEvidence} onChange={(e) => setEntityEvidence(e.target.value)} maxLength={1000} />
      <Checkbox label="The applicant may act for it (confirmed through the organization's own channel)" checked={representative} onChange={() => setRepresentative(!representative)} />
      <TextAreaField label="How the applicant's authority was verified" value={representativeEvidence} onChange={(e) => setRepresentativeEvidence(e.target.value)} maxLength={1000} />
      <TextAreaField label="Decision note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} required />
      {error && <Alert tone="danger" live="assertive" title="Not decided" className="mb-3">{error}</Alert>}
      <div className="btn-list">
        <Button onClick={() => decide("APPROVE")} disabled={!entity || !representative || note.trim().length < 2}>Approve</Button>
        <Button variant="danger" onClick={() => decide("REJECT")} disabled={note.trim().length < 2}>Reject</Button>
      </div>
    </section>
  );
};

const CapabilityDecision: React.FC<{ id: string; summary: string; onDone: () => void }> = ({ id, summary, onDone }) => {
  const withStepUp = useStepUp();
  const [note, setNote] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const decide = async (decision: "APPROVE" | "REJECT") => {
    setError(null);
    try {
      await withStepUp(TRUST_REVIEW_ACTION, id, (token) => decideCapability(id, decision, note, token));
      onDone();
    } catch (cause) {
      setError(describeError(cause));
    }
  };
  return (
    <section className="border rounded p-3 mb-3" aria-label={`Capability request ${id}`}>
      <p className="small mb-2">{summary}</p>
      <TextAreaField label="Decision note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} required />
      {error && <Alert tone="danger" live="assertive" title="Not decided" className="mb-3">{error}</Alert>}
      <div className="btn-list">
        <Button onClick={() => decide("APPROVE")} disabled={note.trim().length < 2}>Approve</Button>
        <Button variant="danger" onClick={() => decide("REJECT")} disabled={note.trim().length < 2}>Reject</Button>
      </div>
    </section>
  );
};
