import React from "react";
import { IconKey, IconUserCheck } from "@tabler/icons-react";
import {
  acceptGuardianInvitation,
  completeGuardianRebind,
  fetchGuardianInvitations,
  fetchGuardians,
  startGuardianRebind,
  type Guardian,
  type GuardianInvitation,
} from "../../api/recovery.ts";
import { Card } from "../../components/ui/Card.tsx";
import { Button } from "../../components/ui/Button.tsx";
import { Alert } from "../../components/ui/Alert.tsx";
import { Badge } from "../../components/ui/StatusBadge.tsx";
import { IdentifierText } from "../../components/ui/IdentifierText.tsx";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States.tsx";
import { useStepUp } from "../../components/ssi/stepUpContext.ts";
import { useAuth } from "../../context/AuthContext.ts";
import { createDeviceKey, findDeviceKey, getOrCreateDeviceKey } from "../../lib/guardianDeviceKey.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { describeError } from "../../lib/http.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

/** Invitations are accepted with a key this browser creates and never reveals. */
export const InvitationsCard: React.FC<{ onChanged: () => void }> = ({ onChanged }) => {
  const { user } = useAuth();
  const withStepUp = useStepUp();
  const invitations = useAsync(fetchGuardianInvitations, []);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  if (invitations.status === "loading") return null;
  if (invitations.status === "error") return <div className="card"><ErrorState error={invitations.error} title="Invitations are unavailable" onRetry={invitations.reload} /></div>;
  const open = invitations.data.filter((item) => item.purpose === "ENROLL");
  if (open.length === 0) return null;

  const accept = async (invitation: GuardianInvitation) => {
    setBusy(invitation.guardianId);
    setError(null);
    try {
      const key = await getOrCreateDeviceKey(user?.id ?? "");
      await withStepUp("recovery.guardian.accept", invitation.guardianId, (token) => acceptGuardianInvitation(invitation, key, token));
      invitations.reload();
      onChanged();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card title="Guardian invitations" subtitle="Someone asked you to help recover their wallet key." flush>
      <ul className="list-group list-group-flush" aria-label="Guardian invitations">
        {open.map((item) => (
          <li key={item.guardianId} className="list-group-item">
            <div className="row align-items-center g-3">
              <div className="col min-w-0">
                <div className="fw-medium">You would be listed as {item.displayName}</div>
                <div className="small text-secondary">Wallet <IdentifierText value={item.walletId} label="wallet" copy={false} /> · open until {formatDateTime(item.expiresAt)}</div>
              </div>
              <div className="col-auto">
                <Button size="sm" loading={busy === item.guardianId} onClick={() => accept(item)} icon={<IconUserCheck aria-hidden="true" />}>Accept with this browser</Button>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {error && <div className="card-body"><Alert tone="danger" live="assertive" title="Invitation not accepted">{error}</Alert></div>}
    </Card>
  );
};

async function loadRoles(userId: string): Promise<{ guardians: Guardian[]; deviceDid: string | null }> {
  const [guardians, key] = await Promise.all([fetchGuardians(), findDeviceKey(userId)]);
  return {
    guardians: guardians.filter((item) => item.guardianUserId === userId && item.status !== "REMOVED" && item.status !== "INVITED"),
    deviceDid: key?.did ?? null,
  };
}

/** Shows whether this browser can act for each Guardian role, and rebinds if not. */
export const GuardianKeysCard: React.FC = () => {
  const { user } = useAuth();
  const withStepUp = useStepUp();
  const roles = useAsync(() => loadRoles(user?.id ?? ""), [user?.id]);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const rebind = async (guardian: Guardian) => {
    setBusy(guardian.guardianId);
    setError(null);
    try {
      const invitation = await startGuardianRebind(guardian.guardianId);
      const key = await createDeviceKey(user?.id ?? "");
      await withStepUp("recovery.guardian.rebind", guardian.guardianId, (token) => completeGuardianRebind(invitation, key, token));
      roles.reload();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card title="Your Guardian key" subtitle="Created in this browser and not exportable. Clearing browser data loses it." flush>
      {roles.status === "loading" && <LoadingState label="Checking this browser" rows={2} />}
      {roles.status === "error" && <ErrorState error={roles.error} title="Guardian roles are unavailable" onRetry={roles.reload} />}
      {roles.status === "success" && roles.data.guardians.length === 0 && <EmptyState title="You are not a guardian yet" />}
      {roles.status === "success" && roles.data.guardians.length > 0 && (
        <ul className="list-group list-group-flush" aria-label="Your guardian roles">
          {roles.data.guardians.map((item) => {
            const usable = item.guardianDid === roles.data.deviceDid;
            return (
              <li key={item.guardianId} className="list-group-item">
                <div className="row align-items-center g-3">
                  <div className="col min-w-0">
                    <div className="fw-medium">{item.displayName} <Badge tone={item.status === "ACTIVE" ? "success" : "warning"}>{humanize(item.status)}</Badge></div>
                    <div className="small text-secondary">
                      {usable ? "This browser holds your key." : "This browser does not hold your key, so it cannot sign decisions."}
                      {item.pendingEffectiveAt && ` Change takes effect ${formatDateTime(item.pendingEffectiveAt)}.`}
                    </div>
                  </div>
                  {!usable && item.status === "ACTIVE" && (
                    <div className="col-auto">
                      <Button size="sm" variant="secondary" loading={busy === item.guardianId} onClick={() => rebind(item)} icon={<IconKey aria-hidden="true" />}>Bind a new key</Button>
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {error && <div className="card-body"><Alert tone="danger" live="assertive" title="Key not bound">{error}</Alert></div>}
    </Card>
  );
};
