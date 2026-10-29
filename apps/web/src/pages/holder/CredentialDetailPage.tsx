import React from "react";
import { useParams } from "react-router-dom";
import { IconRefresh } from "@tabler/icons-react";
import { fetchWalletCredentials } from "../../api/wallet.ts";
import { fetchCredentialStatus, type CredentialStatusSnapshot } from "../../api/status.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Table } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { CredentialStatusBadge, Badge } from "../../components/ui/StatusBadge.tsx";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize, isExpired, renderClaimValue } from "../../lib/format.ts";
import { useHolderWallet } from "./useHolderWallet.ts";

export const CredentialDetailPage: React.FC = () => {
  const { id = "" } = useParams();
  const wallet = useHolderWallet();
  const walletId = wallet.status === "success" ? wallet.data.walletId : null;
  const credentials = useAsync(
    () => (walletId ? fetchWalletCredentials(walletId) : new Promise<never>(() => undefined)),
    [walletId],
  );
  const [live, setLive] = React.useState<CredentialStatusSnapshot | null>(null);
  const [liveError, setLiveError] = React.useState<string | null>(null);
  const [checking, setChecking] = React.useState(false);
  const [showRaw, setShowRaw] = React.useState(false);

  const credential = credentials.status === "success" ? credentials.data.find((item) => item.id === id) ?? null : null;

  const checkStatus = async () => {
    if (!credential) return;
    setChecking(true);
    setLiveError(null);
    try {
      setLive(await fetchCredentialStatus(credential.id));
    } catch (error) {
      setLive(null);
      setLiveError(describeError(error));
    } finally {
      setChecking(false);
    }
  };

  const crumbs = [{ label: "Wallet", to: "/wallet" }, { label: "Credential" }];

  if (wallet.status === "error") {
    return <Page title="Credential details" breadcrumbs={crumbs}><div className="card"><ErrorState error={wallet.error} title="Your wallet could not be opened" onRetry={wallet.reload} /></div></Page>;
  }
  if (credentials.status === "error") {
    return <Page title="Credential details" breadcrumbs={crumbs}><div className="card"><ErrorState error={credentials.error} title="Credentials could not be loaded" onRetry={credentials.reload} /></div></Page>;
  }
  if (credentials.status !== "success") {
    return <Page title="Credential details" breadcrumbs={crumbs}><div className="card"><LoadingState label="Loading credential" /></div></Page>;
  }
  if (!credential) {
    return <Page title="Credential details" breadcrumbs={crumbs}><div className="card"><EmptyState title="Credential not found" description="This credential is not stored in your wallet." /></div></Page>;
  }

  const claims = Object.entries(credential.claims);
  return (
    <Page
      eyebrow="Credential"
      title={humanize(credential.type)}
      breadcrumbs={[{ label: "Wallet", to: "/wallet" }, { label: humanize(credential.type) }]}
      actions={<CredentialStatusBadge status={credential.status} />}
    >
      <Grid cols={2}>
        <Card title="Issuance">
          <DataGrid items={[
            { label: "Issuer", value: <IdentifierText value={credential.issuer} label="issuer DID" /> },
            { label: "Holder", value: <IdentifierText value={credential.holderDid} label="holder DID" /> },
            { label: "Credential ID", value: <IdentifierText value={credential.id} label="credential ID" /> },
            { label: "Valid from", value: formatDateTime(credential.validFrom) },
            { label: "Valid until", value: <>{credential.validUntil ? formatDateTime(credential.validUntil) : "No expiry stated"}{isExpired(credential.validUntil) && <> <Badge tone="warning">Past validUntil</Badge></>}</> },
            { label: "Proof", value: `${credential.proofType || "None"}${credential.cryptosuite ? ` · ${credential.cryptosuite}` : ""}` },
          ]} />
        </Card>

        <Card
          title="Status"
          actions={<Button size="sm" variant="secondary" onClick={checkStatus} loading={checking} icon={<IconRefresh aria-hidden="true" />}>Check current status</Button>}
        >
          <DataGrid items={[
            { label: "Stored status", value: <CredentialStatusBadge status={credential.status} /> },
            credential.statusListId ? { label: "Status list", value: <><IdentifierText value={credential.statusListId} label="status list" /> · index {credential.statusListIndex ?? "?"}</> } : null,
            live ? { label: "Current status", value: <><CredentialStatusBadge status={live.status} /> <span className="small text-secondary">(checked just now)</span></> } : null,
            live?.revoked ? { label: "Revoked", value: `${formatDateTime(live.revokedAt)}${live.revocationReason ? ` · ${live.revocationReason}` : ""}` } : null,
          ]} />
          {liveError && <Alert tone="danger" live="assertive" title="Current status could not be checked" className="mt-3">{liveError}</Alert>}
        </Card>
      </Grid>

      <Card title="Attributes" flush>
        {claims.length === 0 ? <div className="card-body text-secondary">No attributes besides the holder DID.</div> : (
          <Table caption="Credential attributes">
            <thead><tr><th scope="col">Attribute</th><th scope="col">Value</th></tr></thead>
            <tbody>{claims.map(([key, value]) => <tr key={key}><th scope="row" className="fw-medium">{humanize(key)}</th><td data-label="Value">{renderClaimValue(value)}</td></tr>)}</tbody>
          </Table>
        )}
      </Card>

      <Card
        title="Signed credential (JSON)"
        actions={<Button size="sm" variant="ghost" onClick={() => setShowRaw((v) => !v)} aria-expanded={showRaw} aria-controls="raw-credential">{showRaw ? "Hide" : "Show"}</Button>}
        flush
      >
        {showRaw && <div className="card-body"><pre id="raw-credential" className="code-pane" tabIndex={0}>{JSON.stringify(credential.raw, null, 2)}</pre></div>}
      </Card>
    </Page>
  );
};
