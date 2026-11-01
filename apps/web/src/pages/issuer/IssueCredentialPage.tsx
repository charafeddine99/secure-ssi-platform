import React from "react";
import { useSearchParams } from "react-router-dom";
import { IconArrowLeft, IconArrowRight, IconBraces, IconForms, IconRefresh } from "@tabler/icons-react";
import {
  createOid4vciOffer,
  fetchOid4vciIssuerMetadata,
  getOid4vciOffer,
  type Oid4vciOffer,
} from "../../api/issuance.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { SelectField, TextAreaField, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { QrPanel } from "../../components/ui/QrPanel.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize, renderClaimValue } from "../../lib/format.ts";
import {
  GRADUATION_YEAR_RANGE,
  UNIVERSITY_AFFILIATIONS,
  UNIVERSITY_CONFIG_ID,
  UNIVERSITY_DEGREES,
  defaultUniversityForm,
  offerTone,
  parseOfferDraft,
  subjectTemplate,
  universityErrors,
  universitySubject,
  type UniversityForm,
} from "./issuerLogic.ts";

type Step = "details" | "review" | "created";

const TERMINAL = ["CLAIMED", "EXPIRED", "REVOKED"];

export const IssueCredentialPage: React.FC = () => {
  const [params] = useSearchParams();
  const metadata = useAsync((signal) => fetchOid4vciIssuerMetadata(signal), []);
  const [configId, setConfigId] = React.useState("");
  const [subjectJson, setSubjectJson] = React.useState("");
  const [recipientDid, setRecipientDid] = React.useState("");
  const [ttlMinutes, setTtlMinutes] = React.useState("30");
  const [pin, setPin] = React.useState("");
  const [step, setStep] = React.useState<Step>("details");
  const [subject, setSubject] = React.useState<Record<string, unknown> | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [offer, setOffer] = React.useState<Oid4vciOffer | null>(null);
  const [pollError, setPollError] = React.useState<string | null>(null);
  const [uni, setUni] = React.useState<UniversityForm>(() => defaultUniversityForm());
  const [uniErrors, setUniErrors] = React.useState<Partial<Record<keyof UniversityForm, string>>>({});
  const [advanced, setAdvanced] = React.useState(false);
  const structured = configId === UNIVERSITY_CONFIG_ID && !advanced;

  const updateUni = (key: keyof UniversityForm) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const next = { ...uni, [key]: key === "programCode" ? event.target.value.toUpperCase() : event.target.value };
    setUni(next);
    setSubjectJson(JSON.stringify(universitySubject(next), null, 2));
    if (uniErrors[key]) setUniErrors((current) => ({ ...current, [key]: undefined }));
  };

  React.useEffect(() => {
    if (metadata.status !== "success" || configId) return;
    const available = metadata.data.credential_configurations_supported;
    const requested = params.get("credentialConfigurationId") ?? "";
    const initial = available[requested] ? requested : Object.keys(available)[0] ?? "";
    setConfigId(initial);
    setSubjectJson(subjectTemplate(initial));
  }, [metadata.status, metadata.data, params, configId]);

  const refresh = React.useCallback(async (offerId: string) => {
    try {
      setOffer(await getOid4vciOffer(offerId));
      setPollError(null);
    } catch (cause) {
      setPollError(describeError(cause));
    }
  }, []);

  React.useEffect(() => {
    if (!offer || TERMINAL.includes(offer.status.toUpperCase())) return;
    const timer = window.setInterval(() => { void refresh(offer.offerId); }, 5000);
    return () => window.clearInterval(timer);
  }, [offer, refresh]);

  const onReview = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    const ttl = Number(ttlMinutes);
    if (!Number.isInteger(ttl) || ttl < 1 || ttl > 1440) { setError("Offer lifetime must be 1 to 1440 minutes."); return; }
    if (structured) {
      const problems = universityErrors(uni);
      setUniErrors(problems);
      if (Object.keys(problems).length > 0) { setError("Some attributes need attention."); return; }
    }
    const parsed = parseOfferDraft(structured ? JSON.stringify(universitySubject(uni)) : subjectJson, recipientDid.trim(), pin.trim(), configId);
    if ("error" in parsed) { setError(parsed.error); return; }
    setSubject(parsed.subject);
    setStep("review");
  };

  const onCreate = async () => {
    if (!subject || !configId) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createOid4vciOffer({
        credentialConfigurationIds: [configId],
        subjectData: subject,
        recipientDid: recipientDid.trim() || undefined,
        ttlSeconds: Number(ttlMinutes) * 60,
        userPin: pin.trim() || undefined,
      });
      setOffer(created);
      setStep("created");
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setCreating(false);
    }
  };

  const restart = () => { setOffer(null); setSubject(null); setPin(""); setStep("details"); setError(null); };

  const stepOrder = ["details", "review", "created"].indexOf(step);

  return (
    <Page
      eyebrow="Issuer workspace"
      title="Create credential offer"
      breadcrumbs={[{ label: "Issuer", to: "/issuer" }, { label: "Create offer" }]}
    >
      <div className="card">
        <div className="card-body py-3">
          <ol className="steps steps-counter steps-blue my-2" aria-label="Offer progress">
            {(["details", "review", "created"] as Step[]).map((s, i) => (
              <li key={s} className={["step-item", i === stepOrder ? "active" : ""].filter(Boolean).join(" ")} aria-current={i === stepOrder ? "step" : undefined}>
                {s === "details" ? "Details" : s === "review" ? "Review" : "Share with holder"}
                <span className="visually-hidden"> — {i < stepOrder ? "completed" : i === stepOrder ? "current step" : "not started"}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <AsyncView state={metadata} onRetry={metadata.reload} loadingLabel="Loading issuer metadata" errorTitle="Issuer metadata could not be loaded">
        {(data) => {
          const configs = Object.entries(data.credential_configurations_supported);
          if (step === "details") {
            return (
              <form onSubmit={onReview} noValidate>
                <Card
                  title="Offer details"
                  footer={(
                    <div className="d-flex justify-content-end">
                      <Button type="submit" icon={<IconArrowRight aria-hidden="true" />}>Review offer</Button>
                    </div>
                  )}
                >
                  <div className="row">
                    <div className="col-lg-7">
                      <SelectField label="Credential type" value={configId} onChange={(e) => { setConfigId(e.target.value); setSubjectJson(subjectTemplate(e.target.value)); setUni(defaultUniversityForm()); setUniErrors({}); setAdvanced(false); }} required>
                        {configs.map(([id, config]) => <option key={id} value={id}>{config.display?.[0]?.name ?? humanize(id)}</option>)}
                      </SelectField>
                      {configId === UNIVERSITY_CONFIG_ID && (
                        <div className="d-flex align-items-center justify-content-between mb-2">
                          <span className="form-label mb-0">Subject attributes</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => { if (advanced) setUni(defaultUniversityForm()); setAdvanced((value) => !value); }}
                            icon={advanced ? <IconForms aria-hidden="true" /> : <IconBraces aria-hidden="true" />}
                            aria-pressed={advanced}
                          >
                            {advanced ? "Use form" : "Edit as JSON"}
                          </Button>
                        </div>
                      )}
                      {structured ? (
                        <div className="row">
                          <SelectField groupClassName="col-md-6 mb-3" label="Affiliation" value={uni.affiliation} onChange={updateUni("affiliation")} error={uniErrors.affiliation} required>
                            {UNIVERSITY_AFFILIATIONS.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                          </SelectField>
                          <SelectField groupClassName="col-md-6 mb-3" label="Degree" value={uni.degree} onChange={updateUni("degree")} error={uniErrors.degree} required>
                            <option value="">Choose a degree…</option>
                            {UNIVERSITY_DEGREES.map((value) => <option key={value} value={value}>{value}</option>)}
                          </SelectField>
                          <TextField
                            groupClassName="col-md-6 mb-3"
                            label="Programme code"
                            hint="Format SYN-…, e.g. SYN-CS-301."
                            value={uni.programCode}
                            onChange={updateUni("programCode")}
                            error={uniErrors.programCode}
                            className="font-monospace"
                            spellCheck={false}
                            autoComplete="off"
                            required
                          />
                          <TextField
                            groupClassName="col-md-6 mb-3"
                            label="Graduation year"
                            type="number"
                            min={GRADUATION_YEAR_RANGE.min}
                            max={GRADUATION_YEAR_RANGE.max}
                            value={uni.graduationYear}
                            onChange={updateUni("graduationYear")}
                            error={uniErrors.graduationYear}
                            required
                          />
                          <p className="small text-secondary mb-3">Use only data the holder has agreed to have issued.</p>
                        </div>
                      ) : (
                        <TextAreaField
                          label="Subject attributes (JSON)"
                          hint={configId === UNIVERSITY_CONFIG_ID
                            ? `Keys: affiliation (${UNIVERSITY_AFFILIATIONS.join(", ")}), programCode (SYN-…), degree (${UNIVERSITY_DEGREES.join(", ")}), graduationYear.`
                            : "Use only data the holder has agreed to have issued."}
                          rows={10}
                          value={subjectJson}
                          onChange={(e) => setSubjectJson(e.target.value)}
                          spellCheck={false}
                          mono
                          required
                        />
                      )}
                    </div>
                    <div className="col-lg-5">
                      <TextField label="Recipient DID (optional)" hint="Restricts the offer to this wallet DID." value={recipientDid} onChange={(e) => setRecipientDid(e.target.value)} spellCheck={false} autoComplete="off" />
                      <TextField label="Offer lifetime (minutes)" type="number" min={1} max={1440} value={ttlMinutes} onChange={(e) => setTtlMinutes(e.target.value)} required />
                      <TextField label="Transaction code (optional)" hint="4–8 digits. Send it to the holder through a different channel." value={pin} onChange={(e) => setPin(e.target.value)} inputMode="numeric" autoComplete="off" />
                    </div>
                  </div>
                  {error && <Alert tone="danger" live="assertive" title="Check the offer details">{error}</Alert>}
                </Card>
              </form>
            );
          }
          if (step === "review" && subject) {
            return (
              <Card
                title="Review before creating"
                flush
                footer={(
                  <div className="btn-list justify-content-end">
                    <Button variant="secondary" onClick={() => setStep("details")} icon={<IconArrowLeft aria-hidden="true" />} disabled={creating}>Edit</Button>
                    <Button onClick={onCreate} loading={creating}>Create offer</Button>
                  </div>
                )}
              >
                <div className="card-body">
                  <DataGrid items={[
                    { label: "Credential type", value: humanize(configId) },
                    { label: "Recipient", value: recipientDid.trim() || "Any wallet holding the offer link" },
                    { label: "Lifetime", value: `${ttlMinutes} minutes` },
                    { label: "Transaction code", value: pin ? "Required (not shown)" : "Not required" },
                  ]} />
                </div>
                <Table caption="Subject attributes">
                  <thead><tr><th scope="col">Attribute</th><th scope="col">Value</th></tr></thead>
                  <tbody>{Object.entries(subject).map(([k, v]) => <tr key={k}><th scope="row" className="fw-medium">{k}</th><td data-label="Value">{renderClaimValue(v)}</td></tr>)}</tbody>
                </Table>
                {error && <div className="card-body"><Alert tone="danger" live="assertive" title="Offer not created">{error}</Alert></div>}
              </Card>
            );
          }
          if (offer) {
            return (
              <Grid cols={2}>
                <Card
                  title="Offer created"
                  subtitle="Share only with the holder: the link works until claimed."
                  actions={<Badge tone={offerTone(offer.status)}>{humanize(offer.status)}</Badge>}
                  footer={(
                    <div className="btn-list">
                      <Button variant="secondary" size="sm" onClick={() => refresh(offer.offerId)} icon={<IconRefresh aria-hidden="true" />}>Refresh status</Button>
                      <Button variant="ghost" size="sm" onClick={restart}>Create another offer</Button>
                    </div>
                  )}
                >
                  <DataGrid items={[
                    { label: "Credential type", value: offer.credentialConfigurationIds.map(humanize).join(", ") },
                    { label: "Expires", value: formatDateTime(offer.expiresAt) },
                    { label: "Status", value: TERMINAL.includes(offer.status.toUpperCase()) ? humanize(offer.status) : "Waiting for the holder (checked every 5 seconds)" },
                  ]} />
                  {pollError && <Alert tone="warning" title="Status could not be refreshed" className="mt-3">{pollError}</Alert>}
                </Card>
                <Card title="Offer QR code"><QrPanel value={offer.qrPayload || offer.deepLinkUri} label="OID4VCI credential offer" /></Card>
              </Grid>
            );
          }
          return null;
        }}
      </AsyncView>
    </Page>
  );
};
