import React from "react";
import { IconClockHour4, IconFileCertificate, IconFileText, IconHourglassEmpty, IconPlus, IconRefresh, IconSend } from "@tabler/icons-react";
import { fetchIssuerOffers } from "../../api/issuance.ts";
import { Grid, Page } from "../../components/ui/PageHeader.tsx";
import { Card, Stat, Table } from "../../components/ui/Card.tsx";
import { Button, ButtonLink } from "../../components/ui/Button.tsx";
import { AsyncView } from "../../components/ui/AsyncView.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { offerTone } from "./issuerLogic.ts";
import { QuickActions } from "../../components/ssi/QuickActions.tsx";
import { DonutChart } from "../../components/ui/Charts.tsx";
import { EmptyState } from "../../components/ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

export const IssuerDashboard: React.FC = () => {
  const offers = useAsync(() => fetchIssuerOffers(), []);
  return (
    <Page
      eyebrow="Issuer workspace"
      title="Issuance overview"
      actions={<ButtonLink to="/issuer/issue" icon={<IconPlus aria-hidden="true" />}>Create offer</ButtonLink>}
    >
      {offers.status === "success" && (
        <Grid cols={4}>
          <Stat label="Offers created" value={offers.data.length} hint="By this issuer account" icon={<IconSend size={20} />} />
          <Stat label="Claimed" value={offers.data.filter((o) => o.status.toUpperCase() === "CLAIMED").length} hint="Holder completed issuance" icon={<IconFileCertificate size={20} />} tone="green" />
          <Stat label="Waiting" value={offers.data.filter((o) => ["PENDING", "OFFERED"].includes(o.status.toUpperCase())).length} hint="Not yet claimed" icon={<IconClockHour4 size={20} />} tone="azure" />
          <Stat label="Expired" value={offers.data.filter((o) => o.status.toUpperCase() === "EXPIRED").length} hint="Closed without a claim" icon={<IconHourglassEmpty size={20} />} tone="yellow" />
        </Grid>
      )}
      <QuickActions actions={[
        { to: "/issuer/issue", title: "Create an offer", text: "Prepare an OID4VCI credential offer.", icon: <IconPlus size={22} />, tone: "indigo" },
        { to: "/issuer/templates", title: "Credential types", text: "What this issuer can sign.", icon: <IconFileText size={22} />, tone: "teal" },
        { to: "/issuer/revocations", title: "Status & revocation", text: "Check or revoke an issued credential.", icon: <IconHourglassEmpty size={22} />, tone: "orange" },
      ]} />
      <div className="row row-cards row-deck">
        {offers.status === "success" && offers.data.length > 0 && (
          <div className="col-lg-4">
            <Card title="Offer status">
              <DonutChart
                ariaLabel="Offers by status"
                centerLabel="offers"
                data={[
                  { label: "Claimed", value: offers.data.filter((o) => o.status.toUpperCase() === "CLAIMED").length, color: "#22c55e" },
                  { label: "Waiting", value: offers.data.filter((o) => ["PENDING", "OFFERED"].includes(o.status.toUpperCase())).length, color: "var(--tblr-primary)" },
                  { label: "Expired", value: offers.data.filter((o) => o.status.toUpperCase() === "EXPIRED").length, color: "#f59e0b" },
                  { label: "Other", value: offers.data.filter((o) => !["CLAIMED", "PENDING", "OFFERED", "EXPIRED"].includes(o.status.toUpperCase())).length, color: "#94a3b8" },
                ]}
              />
            </Card>
          </div>
        )}
        <div className={offers.status === "success" && offers.data.length > 0 ? "col-lg-8" : "col-12"}>
      <Card
        className="w-100"
        title="Recent offers"
        actions={<Button variant="ghost" size="sm" onClick={offers.reload} icon={<IconRefresh aria-hidden="true" />}>Refresh</Button>}
        flush
      >
        <AsyncView state={offers} onRetry={offers.reload} loadingLabel="Loading offers">
          {(items) => items.length === 0 ? (
            <EmptyState title="No offers yet" action={<ButtonLink to="/issuer/issue" variant="secondary" icon={<IconFileText aria-hidden="true" />}>Create offer</ButtonLink>} />
          ) : (
            <Table caption="Credential offers created by this issuer">
              <thead><tr><th scope="col">Credential type</th><th scope="col">Status</th><th scope="col">Expires</th></tr></thead>
              <tbody>
                {items.slice(0, 25).map((offer) => (
                  <tr key={offer.offerId}>
                    <td data-label="Credential type" className="fw-medium">{offer.credentialConfigurationIds.map(humanize).join(", ")}</td>
                    <td data-label="Status"><Badge tone={offerTone(offer.status)}>{humanize(offer.status)}</Badge></td>
                    <td data-label="Expires" className="text-secondary">{formatDateTime(offer.expiresAt)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </AsyncView>
      </Card>
        </div>
      </div>
    </Page>
  );
};
