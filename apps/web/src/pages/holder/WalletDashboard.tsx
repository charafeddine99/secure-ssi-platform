import React from "react";
import { IconFileCertificate, IconInbox, IconMailForward, IconRefresh, IconSend, IconShieldCheck, IconUsersGroup } from "@tabler/icons-react";
import { fetchWalletCredentials } from "../../api/wallet.ts";
import { claimOid4vciOffer, fetchPendingOffers, type Oid4vciOffer } from "../../api/issuance.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, DataGrid, Stat } from "../../components/ui/Card.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { Button, ButtonLink } from "../../components/ui/Button.tsx";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { useToast } from "../../components/ui/toastContext.ts";
import { CredentialCard } from "../../components/ssi/CredentialCard.tsx";
import { QuickActions } from "../../components/ssi/QuickActions.tsx";
import { useAuth } from "../../context/AuthContext.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";
import { useHolderWallet } from "./useHolderWallet.ts";

export const WalletDashboard: React.FC = () => {
  const { user } = useAuth();
  const toast = useToast();
  const wallet = useHolderWallet();
  const walletId = wallet.status === "success" ? wallet.data.walletId : null;
  const credentials = useAsync(
    () => (walletId ? fetchWalletCredentials(walletId) : new Promise<never>(() => undefined)),
    [walletId],
  );
  const offers = useAsync(() => fetchPendingOffers(), []);
  const [claiming, setClaiming] = React.useState<string | null>(null);
  const [claimError, setClaimError] = React.useState<string | null>(null);

  const accept = async (offer: Oid4vciOffer) => {
    if (wallet.status !== "success") return;
    if (offer.credentialConfigurationIds.length !== 1) {
      setClaimError("This wallet claims one credential type per offer. Ask the issuer for a separate offer per type.");
      return;
    }
    setClaiming(offer.offerId);
    setClaimError(null);
    try {
      const result = await claimOid4vciOffer({
        preAuthorizedCode: offer.preAuthorizedCode,
        walletId: wallet.data.walletId,
        holderDid: wallet.data.holderDid,
        credentialConfigurationId: offer.credentialConfigurationIds[0],
      });
      toast("success", `Credential stored in your wallet (status reported by issuer: ${humanize(result.status)}).`);
      offers.reload();
      credentials.reload();
    } catch (error) {
      setClaimError(describeError(error));
    } finally {
      setClaiming(null);
    }
  };

  const credentialCount = credentials.status === "success" ? credentials.data.length : null;
  const offerCount = offers.status === "success" ? offers.data.length : null;

  return (
    <Page
      eyebrow="Holder wallet"
      title={`Welcome, ${user?.displayName ?? "holder"}`}
      actions={<ButtonLink to="/wallet/scan" icon={<IconInbox aria-hidden="true" />}>Receive or share</ButtonLink>}
    >
      {wallet.status === "loading" && <div className="card"><LoadingState label="Opening your wallet" /></div>}
      {wallet.status === "error" && <div className="card"><ErrorState error={wallet.error} title="Your wallet could not be opened" onRetry={wallet.reload} /></div>}

      <Grid cols={3}>
        <Stat label="Stored credentials" value={credentialCount ?? "—"} hint="In this wallet" icon={<IconFileCertificate size={20} />} />
        <Stat label="Pending offers" value={offerCount ?? "—"} hint="Not yet accepted" icon={<IconMailForward size={20} />} tone="azure" />
        <Stat label="Key custody" value={<span className="fs-3">Server-managed</span>} hint="Private key never reaches this browser" icon={<IconShieldCheck size={20} />} tone="secondary" />
      </Grid>

      <QuickActions actions={[
        { to: "/wallet/scan", title: "Receive a credential", text: "Paste an issuer offer link.", icon: <IconInbox size={22} />, tone: "indigo" },
        { to: "/wallet/scan", title: "Share with a verifier", text: "Answer a presentation request.", icon: <IconSend size={22} />, tone: "teal" },
        { to: "/wallet/security", title: "Recovery & guardians", text: "Set who can help you recover.", icon: <IconShieldCheck size={22} />, tone: "purple" },
        { to: "/guardian", title: "Guardian tasks", text: "Requests from people you guard.", icon: <IconUsersGroup size={22} />, tone: "orange" },
      ]} />

      <div className="row row-cards row-deck">
        <div className="col-lg-7">
          <Card
            className="h-100"
            title="Offers waiting for you"
            actions={<Button variant="ghost" size="sm" onClick={offers.reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
            flush
          >
            {claimError && <div className="card-body pb-0"><Alert tone="danger" live="assertive" title="The credential was not stored">{claimError}</Alert></div>}
            <AsyncView state={offers} onRetry={offers.reload} loadingLabel="Loading offers">
              {(items) => items.length === 0 ? (
                <EmptyState title="No pending offers" />
              ) : (
                <ul className="list-group list-group-flush" aria-label="Pending credential offers">
                  {items.map((offer) => (
                    <li key={offer.offerId} className="list-group-item">
                      <div className="row align-items-center g-3">
                        <div className="col min-w-0">
                          <div className="fw-medium">{offer.credentialConfigurationIds.map(humanize).join(", ")}</div>
                          <div className="small text-secondary">Expires {formatDateTime(offer.expiresAt)} · issuer <IdentifierText value={offer.credentialIssuer} label="issuer" copy={false} /></div>
                        </div>
                        <div className="col-auto">
                          <Button size="sm" onClick={() => accept(offer)} loading={claiming === offer.offerId} disabled={wallet.status !== "success" || (claiming !== null && claiming !== offer.offerId)}>
                            Accept and store
                          </Button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </AsyncView>
          </Card>
        </div>
        <div className="col-lg-5">
          {wallet.status === "success" && (
            <Card
              className="h-100"
              title="Wallet identity"
              footer={<ButtonLink to="/wallet/security" variant="secondary" size="sm" icon={<IconShieldCheck aria-hidden="true" />}>Recovery settings</ButtonLink>}
            >
              <DataGrid items={[
                { label: "Holder DID", value: <IdentifierText value={wallet.data.holderDid} label="holder DID" /> },
                { label: "Account ID", value: <IdentifierText value={user?.id ?? ""} label="account ID" /> },
                { label: "Wallet ID", value: <IdentifierText value={wallet.data.walletId} label="wallet ID" /> },
              ]} />
            </Card>
          )}
        </div>
      </div>

      <section aria-labelledby="credentials-title">
        <h2 id="credentials-title" className="h3 mb-3">Stored credentials</h2>
        {wallet.status !== "success" ? null : (
          <AsyncView state={credentials} onRetry={credentials.reload} loadingLabel="Loading credentials">
            {(items) => items.length === 0 ? (
              <div className="card">
                <EmptyState title="Your wallet is empty" description="Accept an offer to add your first credential." action={<ButtonLink to="/wallet/scan" variant="secondary">Paste an offer link</ButtonLink>} />
              </div>
            ) : (
              <Grid cols={3}>
                {items.map((credential) => <CredentialCard key={credential.id} credential={credential} />)}
              </Grid>
            )}
          </AsyncView>
        )}
      </section>
    </Page>
  );
};
