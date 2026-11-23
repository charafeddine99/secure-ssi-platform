import React from "react";
import { useNavigate } from "react-router-dom";
import {
  decideReissuance,
  fetchIssuerReissuanceRequests,
  fetchMyReissuanceRequests,
  requestReissuance,
} from "../../api/reissuance.ts";
import { Card, Table } from "../ui/Card.tsx";
import { Button } from "../ui/Button.tsx";
import { Alert } from "../ui/Alert.tsx";
import { Badge } from "../ui/StatusBadge.tsx";
import { IdentifierText } from "../ui/IdentifierText.tsx";
import { EmptyState, ErrorState, LoadingState } from "../ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

/** Asks the issuer for a new copy. A signed credential is never edited. */
export const RequestReissuanceCard: React.FC<{ walletId: string; credentialId: string }> = ({ walletId, credentialId }) => {
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const onRequest = async () => {
    setBusy(true);
    setError(null);
    try {
      await requestReissuance(walletId, credentialId);
      setMessage("Request sent. The answer appears on My wallet.");
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="Issued to an older DID?" subtitle="After a wallet key recovery, only the issuer can give you this credential for your new DID.">
      {message && <Alert tone="success" live="polite" className="mb-3">{message}</Alert>}
      {error && <Alert tone="danger" live="assertive" title="Not sent" className="mb-3">{error}</Alert>}
      <Button variant="secondary" size="sm" loading={busy} onClick={onRequest}>Ask the issuer to re-issue</Button>
    </Card>
  );
};

export const HolderReissuanceCard: React.FC = () => {
  const navigate = useNavigate();
  const items = useAsync(fetchMyReissuanceRequests, []);
  return (
    <Card title="Re-issuance requests" subtitle="New copies you asked for after changing your DID." flush>
      {items.status === "loading" && <LoadingState label="Loading requests" rows={2} />}
      {items.status === "error" && <ErrorState error={items.error} title="Requests are unavailable" onRetry={items.reload} />}
      {items.status === "success" && items.data.length === 0 && <EmptyState title="No re-issuance requests" />}
      {items.status === "success" && items.data.length > 0 && (
        <Table caption="Re-issuance requests" stackBelow="md">
          <thead><tr><th scope="col">Credential</th><th scope="col">Requested</th><th scope="col">Status</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
          <tbody>
            {items.data.map((item) => (
              <tr key={item.requestId}>
                <td data-label="Credential">{humanize(item.credentialType)}</td>
                <td data-label="Requested">{formatDateTime(item.createdAt)}</td>
                <td data-label="Status"><Badge tone={item.status === "OFFERED" ? "success" : "neutral"}>{humanize(item.status)}</Badge></td>
                <td data-label="Actions">
                  {item.offerLink && <Button size="sm" onClick={() => navigate("/wallet/scan", { state: { link: item.offerLink } })}>Claim new copy</Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
};

export const IssuerReissuanceCard: React.FC = () => {
  const items = useAsync(fetchIssuerReissuanceRequests, []);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const decide = async (requestId: string, decision: "approve" | "reject") => {
    setBusy(requestId);
    setError(null);
    try {
      await decideReissuance(requestId, decision);
      items.reload();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(null);
    }
  };
  return (
    <Card title="Re-issuance requests" subtitle="Holders whose DID changed. Approving creates a new offer for their current DID; the old credential is not changed." flush>
      {items.status === "loading" && <LoadingState label="Loading requests" rows={2} />}
      {items.status === "error" && <ErrorState error={items.error} title="Requests are unavailable" onRetry={items.reload} />}
      {items.status === "success" && items.data.length === 0 && <EmptyState title="No re-issuance requests" />}
      {items.status === "success" && items.data.length > 0 && (
        <Table caption="Re-issuance requests" stackBelow="md">
          <thead><tr><th scope="col">Credential</th><th scope="col">New DID</th><th scope="col">Status</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
          <tbody>
            {items.data.map((item) => (
              <tr key={item.requestId}>
                <td data-label="Credential">{humanize(item.credentialType)}</td>
                <td data-label="New DID"><IdentifierText value={item.newHolderDid} label="new DID" copy={false} /></td>
                <td data-label="Status"><Badge tone={item.status === "OFFERED" ? "success" : "neutral"}>{humanize(item.status)}</Badge></td>
                <td data-label="Actions">
                  {item.status === "PENDING" && (
                    <div className="btn-list flex-nowrap">
                      <Button size="sm" loading={busy === item.requestId} onClick={() => decide(item.requestId, "approve")}>Approve</Button>
                      <Button size="sm" variant="ghost" onClick={() => decide(item.requestId, "reject")}>Reject</Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {error && <div className="card-body"><Alert tone="danger" live="assertive" title="Not completed">{error}</Alert></div>}
    </Card>
  );
};
