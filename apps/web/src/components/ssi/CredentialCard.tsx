import React from "react";
import { Link } from "react-router-dom";
import { IconArrowBackUp, IconArrowRight, IconRotate2, IconSend, IconShieldCheck } from "@tabler/icons-react";
import type { WalletCredential } from "../../api/wallet.ts";
import { fetchCredentialStatus } from "../../api/status.ts";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDate, humanize, renderClaimValue, shortenIdentifier } from "../../lib/format.ts";
import { cardStatus, type CardStatus, type LiveCheck } from "../../utils/cardStatus.ts";

/** Issuer trust comes from the trust registry, separately from credential status. */
export interface IssuerTrust {
  name: string | null;
  state: "TRUSTED" | "SUSPENDED" | "REVOKED" | "NOT_LISTED" | "UNKNOWN";
}

const TRUST_TEXT: Record<IssuerTrust["state"], string> = {
  TRUSTED: "Trusted issuer",
  SUSPENDED: "Issuer suspended",
  REVOKED: "Issuer revoked",
  NOT_LISTED: "Issuer not in registry",
  UNKNOWN: "Issuer trust unknown",
};

/**
 * The issuer's current answer, not the copy kept in the wallet. The mapping
 * itself lives in cardStatus so every state is unit tested.
 */
function useLiveStatus(credential: WalletCredential): CardStatus {
  const live = useAsync(() => fetchCredentialStatus(credential.id), [credential.id]);
  return cardStatus(credential.validUntil, live as LiveCheck, Date.now(), credential.validFrom);
}

/** Stable hue per credential type so the same type always gets the same pass colour. */
function hueFor(type: string): number {
  let hash = 0;
  for (const char of type) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  return hash;
}

/**
 * Wallet-pass style credential. The front shows identity and validity; the
 * back lists the signed attributes. Stored status is shown as stored, never
 * as "verified": only a verifier's policy decides that.
 */
export const CredentialCard: React.FC<{ credential: WalletCredential; trust?: IssuerTrust }> = ({ credential, trust }) => {
  const [flipped, setFlipped] = React.useState(false);
  const status = useLiveStatus(credential);
  const trustState = trust?.state ?? "UNKNOWN";
  const inactive = status.inactive;
  const claims = Object.entries(credential.claims).slice(0, 6);
  const titleId = `cred-${credential.id}`;
  const detailsHref = `/wallet/credentials/${encodeURIComponent(credential.id)}`;
  const style = { "--pass-hue": hueFor(credential.type) } as React.CSSProperties;

  return (
    <article className={["ssi-pass", flipped ? "is-flipped" : "", inactive ? "is-inactive" : ""].filter(Boolean).join(" ")} style={style} aria-labelledby={titleId}>
      <div className="ssi-pass-inner">
        <div className="ssi-pass-face ssi-pass-front" aria-hidden={flipped}>
          <div className="d-flex align-items-start justify-content-between gap-3">
            <div className="min-w-0">
              <div className="ssi-pass-kicker">Verifiable credential</div>
              <h3 className="ssi-pass-title" id={titleId}>{humanize(credential.type)}</h3>
            </div>
            <span className="ssi-pass-chip" aria-hidden="true"><IconShieldCheck size={22} /></span>
          </div>

          <div className="ssi-pass-issuer">
            <span className="ssi-pass-label">Issuer</span>
            {trust?.name && <span className="ssi-pass-issuer-name">{trust.name}</span>}
            <span className="ssi-pass-mono" title={credential.issuer}>{shortenIdentifier(credential.issuer)}</span>
            <span className={`ssi-pass-trust ssi-pass-trust-${trustState.toLowerCase()}`}>{TRUST_TEXT[trustState]}</span>
          </div>

          <div className="d-flex align-items-end justify-content-between gap-3 mt-auto">
            <dl className="ssi-pass-dates mb-0">
              <div><dt>Valid from</dt><dd>{formatDate(credential.validFrom)}</dd></div>
              <div><dt>Valid until</dt><dd>{credential.validUntil ? formatDate(credential.validUntil) : "No expiry"}</dd></div>
              <div>
                <dt>Credential status</dt>
                <dd><span className={`ssi-pass-status ssi-pass-status-${status.key}`} aria-live="polite">{status.text}</span></dd>
              </div>
            </dl>
          </div>

          {status.blocked && <p className="ssi-pass-note mb-0" id={`${titleId}-blocked`}>{status.blocked} It cannot be presented.</p>}
          <div className="ssi-pass-actions">
            {status.blocked ? (
              <button type="button" className="ssi-pass-btn" disabled aria-describedby={`${titleId}-blocked`} tabIndex={flipped ? -1 : 0}>
                <IconSend size={16} aria-hidden="true" /> Present<span className="visually-hidden"> {humanize(credential.type)}</span>
              </button>
            ) : (
              <Link className="ssi-pass-btn" to="/wallet/scan" state={{ present: true }} tabIndex={flipped ? -1 : 0}>
                <IconSend size={16} aria-hidden="true" /> Present<span className="visually-hidden"> {humanize(credential.type)}</span>
              </Link>
            )}
            <button type="button" className="ssi-pass-btn" onClick={() => setFlipped(true)} tabIndex={flipped ? -1 : 0} aria-label={`Show attributes of ${humanize(credential.type)}`}>
              <IconRotate2 size={16} aria-hidden="true" /> Attributes
            </button>
            <Link className="ssi-pass-btn" to={detailsHref} tabIndex={flipped ? -1 : 0}>
              Details <IconArrowRight size={16} aria-hidden="true" /><span className="visually-hidden"> for {humanize(credential.type)}</span>
            </Link>
          </div>
        </div>

        <div className="ssi-pass-face ssi-pass-back" aria-hidden={!flipped}>
          <div className="ssi-pass-kicker mb-2">Signed attributes</div>
          {claims.length === 0 ? (
            <p className="small mb-0 opacity-75">No attributes besides the holder DID.</p>
          ) : (
            <dl className="ssi-pass-claims mb-0">
              {claims.map(([key, value]) => (
                <div key={key}><dt>{humanize(key)}</dt><dd>{renderClaimValue(value)}</dd></div>
              ))}
            </dl>
          )}
          <div className="ssi-pass-actions">
            <button type="button" className="ssi-pass-btn" onClick={() => setFlipped(false)} tabIndex={flipped ? 0 : -1} aria-label="Show the front of the credential">
              <IconArrowBackUp size={16} aria-hidden="true" /> Front
            </button>
            <Link className="ssi-pass-btn" to={detailsHref} tabIndex={flipped ? 0 : -1}>
              All details <IconArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
};
