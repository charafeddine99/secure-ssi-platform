import React from "react";
import { useLocation } from "react-router-dom";
import { IconSend, IconX } from "@tabler/icons-react";
import {
  createWalletOid4vpPresentation,
  evaluateOid4vpSession,
  getOid4vpHolderRequest,
  recordWalletOid4vpConsent,
  submitOid4vpDirectPost,
  type Oid4vpHolderRequest,
  type VerificationResult,
} from "../../api/presentation.ts";
import { fetchWalletCredentials, getOrCreateHolderWallet, type HolderWallet, type WalletCredential } from "../../api/wallet.ts";
import { Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button, ButtonLink } from "../../components/ui/Button.tsx";
import { Checkbox } from "../../components/ui/Field.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { PolicyBanner, VerificationMatrix } from "../../components/ssi/VerificationMatrix.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize, renderClaimValue } from "../../lib/format.ts";
import { getOid4vpSubmissionErrorMessage, type Oid4vpSubmissionStage } from "../../utils/oid4vpSubmissionError.ts";

interface ConsentContext {
  request: Oid4vpHolderRequest;
  wallet: HolderWallet;
  matches: WalletCredential[];
}

type Outcome =
  | { kind: "accepted"; result: VerificationResult | null }
  | { kind: "policy-rejected"; result: VerificationResult | null; status: string }
  | { kind: "declined" }
  | { kind: "error"; message: string };

/**
 * Load the verifier session and the holder's ACTIVE credentials, then ask the
 * backend which credentials satisfy the DCQL query. Every failure is thrown.
 */
async function loadConsentContext(sessionId: string): Promise<ConsentContext> {
  if (!sessionId) throw new Error("Open this page from a verifier request. No request identifier was supplied.");
  const request = await getOid4vpHolderRequest(sessionId);
  if (request.status !== "PENDING" || (request.consentStatus && request.consentStatus !== "PENDING")) {
    throw new Error(`This request is ${humanize(request.status).toLowerCase()} and can no longer receive a decision.`);
  }
  const wallet = await getOrCreateHolderWallet();
  const credentials = (await fetchWalletCredentials(wallet.walletId)).filter(
    (credential) => credential.status === "ACTIVE" && Object.keys(credential.raw).length > 0,
  );
  if (credentials.length === 0) throw new Error("Your wallet has no active credential that could answer this request.");
  const evaluation = await evaluateOid4vpSession(sessionId, credentials.map((credential) => credential.raw));
  if (!evaluation.isSatisfied) {
    throw new Error(evaluation.unsatisfiedReason || "No credential in your wallet satisfies this request.");
  }
  const queryIds = evaluation.details?.selectedQueryIds
    ?? [...new Set(evaluation.matchedCredentials.map((match) => match.queryId))];
  if (queryIds.length !== 1) {
    throw new Error("This wallet answers one DCQL credential query at a time. Nothing was shared.");
  }
  const matchedIds = new Set(
    evaluation.matchedCredentials.filter((match) => match.queryId === queryIds[0]).map((match) => match.credentialId),
  );
  const matches = credentials.filter((credential) => matchedIds.has(credential.id));
  if (matches.length === 0) throw new Error("The request did not match an active credential in your wallet.");
  return { request, wallet, matches };
}

export const PresentationConsentPage: React.FC = () => {
  const location = useLocation();
  const sessionId = React.useMemo(() => {
    const fromState = (location.state as { sessionId?: unknown } | null)?.sessionId;
    if (typeof fromState === "string" && fromState) return fromState;
    return new URLSearchParams(location.search).get("sessionId") ?? "";
  }, [location.search, location.state]);

  const context = useAsync(() => loadConsentContext(sessionId), [sessionId]);
  const [selectedId, setSelectedId] = React.useState("");
  const [consent, setConsent] = React.useState(false);
  const [busy, setBusy] = React.useState<"approve" | "reject" | "retry" | null>(null);
  const [prepared, setPrepared] = React.useState<Parameters<typeof submitOid4vpDirectPost>[0] | null>(null);
  const [blocked, setBlocked] = React.useState(false);
  const [outcome, setOutcome] = React.useState<Outcome | null>(null);

  React.useEffect(() => {
    if (context.status === "success") setSelectedId(context.data.matches[0].id);
  }, [context.status, context.data]);

  const selected = context.status === "success" ? context.data.matches.find((c) => c.id === selectedId) ?? null : null;
  const claims = selected?.claims ?? {};
  const claimEntries = Object.entries(claims);
  const finished = outcome !== null && outcome.kind !== "error";

  const deliver = async (payload: Parameters<typeof submitOid4vpDirectPost>[0]) => {
    const response = await submitOid4vpDirectPost(payload);
    setPrepared(null);
    if (response.result?.finalPolicyResult === "ACCEPTED") {
      setOutcome({ kind: "accepted", result: response.result });
    } else {
      setOutcome({ kind: "policy-rejected", result: response.result, status: response.status });
    }
  };

  const onApprove = async () => {
    if (context.status !== "success" || !selected || !consent || prepared || blocked || claimEntries.length === 0) return;
    const { request, wallet } = context.data;
    setBusy("approve");
    setOutcome(null);
    let stage: Oid4vpSubmissionStage = "consent";
    try {
      await recordWalletOid4vpConsent({
        sessionId: request.sessionId,
        walletId: wallet.walletId,
        holderDid: wallet.holderDid,
        action: "APPROVE",
        approvedCredentials: [selected.id],
        approvedClaims: claims,
      });
      stage = "presentation";
      const presentation = await createWalletOid4vpPresentation({
        sessionId: request.sessionId,
        walletId: wallet.walletId,
        credentialIds: [selected.id],
        disclosedClaims: claims,
      });
      const payload = { sessionId: request.sessionId, vpToken: presentation.vpToken, disclosedClaims: claims };
      setPrepared(payload);
      stage = "direct-post";
      await deliver(payload);
    } catch (error) {
      if (stage !== "direct-post") {
        setPrepared(null);
        setBlocked(true);
      }
      setOutcome({ kind: "error", message: getOid4vpSubmissionErrorMessage(error, stage) });
    } finally {
      setBusy(null);
    }
  };

  const onRetry = async () => {
    if (!prepared || busy) return;
    setBusy("retry");
    setOutcome(null);
    try {
      await deliver(prepared);
    } catch (error) {
      setOutcome({ kind: "error", message: getOid4vpSubmissionErrorMessage(error, "direct-post") });
    } finally {
      setBusy(null);
    }
  };

  const onReject = async () => {
    if (context.status !== "success" || busy) return;
    const { request, wallet } = context.data;
    setBusy("reject");
    setOutcome(null);
    try {
      await recordWalletOid4vpConsent({
        sessionId: request.sessionId,
        walletId: wallet.walletId,
        holderDid: wallet.holderDid,
        action: "REJECT",
        rejectionReason: "Holder declined the verification request.",
      });
      setOutcome({ kind: "declined" });
    } catch (error) {
      setOutcome({ kind: "error", message: describeError(error) });
    } finally {
      setBusy(null);
    }
  };

  return (
    <Page
      eyebrow="Consent"
      title="Review a verification request"
      description="The complete signed credential is shared."
      breadcrumbs={[{ label: "Wallet", to: "/wallet" }, { label: "Consent" }]}
      narrow
    >
      {context.status === "loading" && <div className="card"><LoadingState label="Loading the request and your matching credentials" /></div>}
      {context.status === "error" && (
        <div className="card"><ErrorState error={context.error} title="This request cannot be answered" onRetry={sessionId ? context.reload : undefined} /></div>
      )}

      {context.status === "success" && (
        <>
          <Card title="Who is asking">
            <DataGrid items={[
              { label: "Verifier", value: <IdentifierText value={context.data.request.clientId || context.data.request.verifierDid} label="verifier" /> },
              { label: "Purpose", value: context.data.request.purpose || "No purpose supplied" },
              { label: "Requested fields", value: context.data.request.requestedFields.length ? context.data.request.requestedFields.map(humanize).join(", ") : "Not listed" },
              { label: "Expires", value: formatDateTime(context.data.request.expiresAt) },
            ]} />
          </Card>

          <Card title="What would be shared" flush>
            <div className="card-body">
              {context.data.matches.length > 1 && (
                <fieldset className="mb-3">
                  <legend className="form-label">Choose a credential</legend>
                  {context.data.matches.map((credential) => (
                    <Checkbox
                      key={credential.id}
                      type="radio"
                      name="credential"
                      value={credential.id}
                      checked={selectedId === credential.id}
                      onChange={() => setSelectedId(credential.id)}
                      disabled={busy !== null || prepared !== null || finished}
                      label={`${humanize(credential.type)} · valid until ${credential.validUntil ? formatDateTime(credential.validUntil) : "no expiry"}`}
                    />
                  ))}
                </fieldset>
              )}
              {selected && (
                <>
                  <p className="text-secondary">{humanize(selected.type)} from <IdentifierText value={selected.issuer} label="issuer" copy={false} /></p>
                  <Alert tone="warning" title={`All ${claimEntries.length} attributes below will be disclosed`}>
                    The verifier receives the full signed credential, including attributes it did not ask for.
                  </Alert>
                </>
              )}
            </div>
            {selected && (
              <Table caption="Attributes in the selected credential">
                <thead><tr><th scope="col">Attribute</th><th scope="col">Value</th></tr></thead>
                <tbody>
                  {claimEntries.map(([key, value]) => (
                    <tr key={key}><th scope="row" className="fw-medium">{humanize(key)}</th><td data-label="Value">{renderClaimValue(value)}</td></tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>

          {outcome?.kind === "accepted" && (
            <Alert tone="success" live="polite" title="The verifier accepted the presentation" actions={<ButtonLink to="/wallet" size="sm" variant="secondary">Back to wallet</ButtonLink>}>
              This is the verifier's backend policy decision, not a decision made in your browser.
            </Alert>
          )}
          {outcome?.kind === "policy-rejected" && (
            <Alert tone="warning" live="polite" title="The verifier did not accept the presentation" actions={<ButtonLink to="/wallet" size="sm" variant="secondary">Back to wallet</ButtonLink>}>
              The presentation was delivered and evaluated; the result was {outcome.result?.finalPolicyResult ?? humanize(outcome.status)}.
            </Alert>
          )}
          {(outcome?.kind === "accepted" || outcome?.kind === "policy-rejected") && outcome.result && (
            <><PolicyBanner result={outcome.result} /><Card title="Verification checks reported by the verifier" flush><VerificationMatrix result={outcome.result} /></Card></>
          )}
          {outcome?.kind === "declined" && (
            <Alert tone="neutral" live="polite" title="You declined this request" actions={<ButtonLink to="/wallet" size="sm" variant="secondary">Back to wallet</ButtonLink>}>
              Nothing was shared. The verifier sees that the request was rejected.
            </Alert>
          )}
          {outcome?.kind === "error" && (
            <Alert
              tone="danger"
              live="assertive"
              title="The request was not completed"
              actions={prepared ? <Button size="sm" onClick={onRetry} loading={busy === "retry"}>Retry delivery of the same presentation</Button> : undefined}
            >
              {outcome.message}
              {blocked && " Approval is disabled for this request; ask the verifier for a new one."}
            </Alert>
          )}

          {!finished && (
            <Card
              title="Your decision"
              footer={(
                <div className="btn-list">
                  <Button
                    onClick={onApprove}
                    disabled={!consent || !selected || prepared !== null || blocked || (busy !== null && busy !== "approve")}
                    loading={busy === "approve"}
                    icon={<IconSend aria-hidden="true" />}
                  >
                    Share credential
                  </Button>
                  <Button
                    variant="danger"
                    onClick={onReject}
                    disabled={prepared !== null || (busy !== null && busy !== "reject")}
                    loading={busy === "reject"}
                    icon={<IconX aria-hidden="true" />}
                  >
                    Decline
                  </Button>
                </div>
              )}
            >
              <Checkbox
                className="mb-0"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
                disabled={busy !== null || prepared !== null || blocked}
                label="I agree to send this complete credential to the verifier named above for the stated purpose."
              />
            </Card>
          )}
        </>
      )}
    </Page>
  );
};
