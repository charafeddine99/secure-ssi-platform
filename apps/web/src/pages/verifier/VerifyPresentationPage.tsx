import React from "react";
import { IconSearch } from "@tabler/icons-react";
import { verifyPresentation, type PresentationVerificationResult } from "../../api/presentation.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { TextAreaField, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { extractPresentation } from "./verifierLogic.ts";

const STATUS_COPY: Record<PresentationVerificationResult["status"], { tone: "success" | "danger" | "warning"; title: string }> = {
  VERIFIED: { tone: "success", title: "Verified" },
  REJECTED: { tone: "danger", title: "Not verified" },
  UNAVAILABLE: { tone: "warning", title: "Verification service unavailable — not verified" },
  ERROR: { tone: "danger", title: "Verification error — not verified" },
};

export const VerifyPresentationPage: React.FC = () => {
  const [json, setJson] = React.useState("");
  const [challenge, setChallenge] = React.useState("");
  const [domain, setDomain] = React.useState("");
  const [formError, setFormError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<PresentationVerificationResult | null>(null);

  const onVerify = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    setResult(null);
    const vp = extractPresentation(json);
    if (typeof vp === "string") { setFormError(vp); return; }
    if (challenge.trim().length < 16) { setFormError("Enter the challenge you issued (at least 16 characters)."); return; }
    if (!domain.trim()) { setFormError("Enter the domain you issued for this presentation."); return; }
    setBusy(true);
    try {
      setResult(await verifyPresentation({ presentation: vp, expectedChallenge: challenge.trim(), expectedDomain: domain.trim() }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page
      eyebrow="Verifier workspace"
      title="Verify a presentation"
      breadcrumbs={[{ label: "Verifier", to: "/verifier" }, { label: "Verify presentation" }]}
    >
      <div className="row row-cards">
        <div className={result ? "col-lg-7" : "col-12"}>
          <form onSubmit={onVerify} noValidate>
            <Card title="Presentation" footer={<Button type="submit" loading={busy} icon={<IconSearch aria-hidden="true" />}>Verify</Button>}>
              <TextAreaField label="Verifiable Presentation (JSON)" rows={10} value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} mono required />
              <div className="row">
                <TextField groupClassName="col-md-6 mb-3" label="Expected challenge" value={challenge} onChange={(e) => setChallenge(e.target.value)} spellCheck={false} autoComplete="off" required />
                <TextField groupClassName="col-md-6 mb-3" label="Expected domain" value={domain} onChange={(e) => setDomain(e.target.value)} spellCheck={false} autoComplete="off" required />
              </div>
              {formError && <Alert tone="danger" live="assertive" title="Check the input">{formError}</Alert>}
            </Card>
          </form>
        </div>
        {result && (
          <div className="col-lg-5">
            <Card title="Result" actions={<Badge tone={STATUS_COPY[result.status].tone}>{STATUS_COPY[result.status].title}</Badge>} status={STATUS_COPY[result.status].tone}>
              <Alert tone={STATUS_COPY[result.status].tone} live="polite" title={STATUS_COPY[result.status].title} className="mb-4">
                {result.verified ? "The server accepted the presentation under the current policy." : result.errors.join(" ") || "The presentation was not accepted."}
              </Alert>
              <DataGrid items={[
                { label: "Signature", value: result.signature_valid === undefined ? "Not reported" : result.signature_valid ? "Valid" : "Invalid" },
                { label: "Challenge", value: result.challenge_valid === undefined ? "Not reported" : result.challenge_valid ? "Matches" : "Does not match" },
              ]} />
            </Card>
          </div>
        )}
      </div>
    </Page>
  );
};
