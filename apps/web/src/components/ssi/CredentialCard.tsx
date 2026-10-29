import React from "react";
import { Link } from "react-router-dom";
import QRCode from "qrcode";
import { IconArrowBackUp, IconArrowRight, IconRotate2, IconShieldCheck } from "@tabler/icons-react";
import type { WalletCredential } from "../../api/wallet.ts";
import { formatDate, humanize, isExpired, renderClaimValue, shortenIdentifier } from "../../lib/format.ts";

const STATUS_TEXT: Record<WalletCredential["status"], string> = {
  ACTIVE: "Active · stored",
  SUSPENDED: "Suspended",
  REVOKED: "Revoked",
  EXPIRED: "Expired",
  UNKNOWN: "Status unknown",
};

/** Stable hue per credential type so the same type always gets the same pass colour. */
function hueFor(type: string): number {
  let hash = 0;
  for (const char of type) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  return hash;
}

function useQrDataUrl(value: string): string | null {
  const [url, setUrl] = React.useState<string | null>(null);
  React.useEffect(() => {
    let alive = true;
    QRCode.toDataURL(value, { margin: 0, width: 160, color: { dark: "#0b1222", light: "#ffffff" } })
      .then((data) => { if (alive) setUrl(data); })
      .catch(() => { if (alive) setUrl(null); });
    return () => { alive = false; };
  }, [value]);
  return url;
}

/**
 * Wallet-pass style credential. The front shows identity and validity; the
 * back lists the signed attributes. Stored status is shown as stored, never
 * as "verified": only a verifier's policy decides that.
 */
export const CredentialCard: React.FC<{ credential: WalletCredential }> = ({ credential }) => {
  const [flipped, setFlipped] = React.useState(false);
  const qr = useQrDataUrl(credential.id);
  const expiredByDate = credential.status === "ACTIVE" && isExpired(credential.validUntil);
  const inactive = credential.status !== "ACTIVE" || expiredByDate;
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
            <span className="ssi-pass-mono" title={credential.issuer}>{shortenIdentifier(credential.issuer)}</span>
          </div>

          <div className="d-flex align-items-end justify-content-between gap-3 mt-auto">
            <dl className="ssi-pass-dates mb-0">
              <div><dt>Valid from</dt><dd>{formatDate(credential.validFrom)}</dd></div>
              <div><dt>Valid until</dt><dd>{credential.validUntil ? formatDate(credential.validUntil) : "No expiry"}</dd></div>
              <div>
                <dt>Status</dt>
                <dd><span className={`ssi-pass-status ssi-pass-status-${credential.status.toLowerCase()}`}>{expiredByDate ? "Past validUntil" : STATUS_TEXT[credential.status]}</span></dd>
              </div>
            </dl>
            {qr && <img className="ssi-pass-qr" src={qr} alt={`QR code of credential ID ${credential.id}`} width={72} height={72} />}
          </div>

          <div className="ssi-pass-actions">
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
