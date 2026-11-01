import React from "react";
import { useNavigate } from "react-router-dom";
import { IconClipboardText, IconFileCertificate, IconSend } from "@tabler/icons-react";
import { claimOid4vciOffer, IssuanceStepError, type IssuanceStep } from "../../api/issuance.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid } from "../../components/ui/Card.tsx";
import { Button, ButtonLink } from "../../components/ui/Button.tsx";
import { Checkbox, TextAreaField, TextField } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { describeError } from "../../lib/http.ts";
import { humanize } from "../../lib/format.ts";
import { parseOid4vpRequestSessionId } from "../../utils/oid4vpRequestUri.ts";
import { useHolderWallet } from "./useHolderWallet.ts";
import { parseCredentialOfferUri, type ParsedOffer } from "./offerUri.ts";

const STEP_LABELS: Record<IssuanceStep, string> = {
  token: "Exchanging the pre-authorized code for an access token",
  metadata: "Reading issuer metadata",
  proof: "Signing the holder proof with your wallet key",
  credential: "Requesting the signed credential",
};

export const ScanQrPage: React.FC = () => {
  const navigate = useNavigate();
  const wallet = useHolderWallet();
  const [input, setInput] = React.useState("");
  const [parseError, setParseError] = React.useState<string | null>(null);
  const [offer, setOffer] = React.useState<ParsedOffer | null>(null);
  const [consent, setConsent] = React.useState(false);
  const [txCode, setTxCode] = React.useState("");
  const [step, setStep] = React.useState<IssuanceStep | null>(null);
  const [claimError, setClaimError] = React.useState<string | null>(null);
  const [claimed, setClaimed] = React.useState<{ credentialId: string; status: string } | null>(null);

  const onReview = (event: React.FormEvent) => {
    event.preventDefault();
    setParseError(null);
    setOffer(null);
    setClaimed(null);
    setClaimError(null);
    setConsent(false);
    setTxCode("");
    const value = input.trim();
    if (!value) {
      setParseError("Paste an openid-credential-offer:// or openid4vp:// link.");
      return;
    }
    try {
      if (value.startsWith("openid-credential-offer://")) {
        setOffer(parseCredentialOfferUri(value));
        return;
      }
      if (value.startsWith("openid4vp://")) {
        const sessionId = parseOid4vpRequestSessionId(value);
        navigate(`/wallet/consent?sessionId=${encodeURIComponent(sessionId)}`);
        return;
      }
      setParseError("Unrecognised link. It must start with openid-credential-offer:// or openid4vp://.");
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "The link could not be read.");
    }
  };

  const onAccept = async () => {
    if (!offer || !consent || wallet.status !== "success" || step) return;
    if (offer.requiresTxCode && !txCode.trim()) {
      setClaimError("Enter the transaction code the issuer gave you.");
      return;
    }
    setClaimError(null);
    try {
      const result = await claimOid4vciOffer({
        preAuthorizedCode: offer.preAuthorizedCode,
        walletId: wallet.data.walletId,
        holderDid: wallet.data.holderDid,
        credentialConfigurationId: offer.configurationId,
        userPin: offer.requiresTxCode ? txCode.trim() : undefined,
        onStep: setStep,
      });
      setClaimed({ credentialId: result.credentialId, status: result.status });
      setOffer(null);
    } catch (error) {
      const where = error instanceof IssuanceStepError ? ` (stopped at: ${STEP_LABELS[error.step].toLowerCase()})` : "";
      setClaimError(`${describeError(error)}${where}`);
    } finally {
      setStep(null);
    }
  };

  return (
    <Page
      eyebrow="Wallet action"
      title="Receive or share"
      description="Paste an offer or a verification request."
      breadcrumbs={[{ label: "Wallet", to: "/wallet" }, { label: "Receive or share" }]}
      narrow
    >
      <Card title="Paste a link">
        <form onSubmit={onReview} noValidate>
          <TextAreaField
            label="Offer or request link"
            hint="openid-credential-offer://… (OID4VCI) or openid4vp://… (OID4VP)"
            rows={4}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            error={parseError}
            spellCheck={false}
            autoComplete="off"
            mono
          />
          <Button type="submit" icon={<IconClipboardText aria-hidden="true" />}>Review link</Button>
        </form>
      </Card>

      {offer && (
        <Card title="Review credential offer" status="primary">
          {wallet.status === "loading" && <LoadingState label="Opening your wallet" rows={1} />}
          {wallet.status === "error" && <ErrorState error={wallet.error} title="Your wallet could not be opened" onRetry={wallet.reload} />}
          <DataGrid className="mb-4" items={[
            { label: "Credential type", value: humanize(offer.configurationId) },
            { label: "Issuer", value: offer.issuer ? <IdentifierText value={offer.issuer} label="issuer" /> : "Not stated in the offer" },
            wallet.status === "success" ? { label: "Bound to", value: <IdentifierText value={wallet.data.holderDid} label="holder DID" /> } : null,
          ]} />
          {offer.requiresTxCode && (
            <TextField
              label="Transaction code"
              hint={offer.txCodeDescription ?? "The issuer sends this code through a separate channel."}
              value={txCode}
              onChange={(event) => setTxCode(event.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              required
            />
          )}
          <Checkbox
            className="mb-3"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            label="I want this issuer to issue the credential to my wallet. My wallet will sign a proof with its server-managed key."
          />
          <div className="vstack gap-3">
            {step && <Alert tone="info" live="polite" title="Issuance in progress">{STEP_LABELS[step]}…</Alert>}
            {claimError && <Alert tone="danger" live="assertive" title="The credential was not stored">{claimError}</Alert>}
            <div className="btn-list">
              <Button onClick={onAccept} disabled={!consent || wallet.status !== "success"} loading={step !== null} icon={<IconFileCertificate aria-hidden="true" />}>
                Accept and store
              </Button>
              <Button variant="secondary" onClick={() => setOffer(null)} disabled={step !== null}>Discard</Button>
            </div>
          </div>
        </Card>
      )}

      {claimed && (
        <Alert
          tone="success"
          live="polite"
          title="Credential stored"
          actions={<ButtonLink to={`/wallet/credentials/${encodeURIComponent(claimed.credentialId)}`} size="sm" variant="secondary">View credential</ButtonLink>}
        >
          The issuer returned a signed credential and it is now in your wallet. Status reported by the issuer: {humanize(claimed.status)}.
        </Alert>
      )}

      <p className="small text-secondary mb-0 d-flex align-items-center gap-2"><IconSend size={16} aria-hidden="true" /> You review every request before anything leaves your wallet.</p>
    </Page>
  );
};
