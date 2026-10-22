import React from "react";
import { Building2, CalendarDays, Eye, FileBadge2, QrCode } from "lucide-react";
import { StatusChip } from "../common/StatusChip";
import type { CredentialStatus } from "../../services/api";

export interface CredentialCardData {
  id: string;
  title: string;
  category: string;
  issuerName: string;
  issuer: string;
  issuedDate: string;
  expiryDate: string;
  status: CredentialStatus;
  claims: Record<string, unknown>;
  proofValue: string;
  aiRiskScore?: number;
}

interface CredentialCardProps {
  credential: CredentialCardData;
  onViewDetails?: (cred: CredentialCardData) => void;
  onPresent?: (cred: CredentialCardData) => void;
}

function displayDate(value: string): string {
  if (!value) return "Not supplied";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function displayCategory(value: string): string {
  return value.replace(/[_-]+/g, " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export const CredentialCard: React.FC<CredentialCardProps> = ({ credential, onViewDetails, onPresent }) => (
  <article className="holder-credential-card" data-category={credential.category.toLowerCase()}>
    <header className="holder-credential-card__header">
      <div className="holder-credential-card__identity">
        <span className="holder-credential-card__mark" aria-hidden="true"><FileBadge2 size={21} /></span>
        <div className="holder-credential-card__title-wrap">
          <p className="holder-credential-card__category">{displayCategory(credential.category)} credential</p>
          <h3>{credential.title}</h3>
        </div>
      </div>
      <StatusChip status={credential.status} size="sm" />
    </header>

    <div className="holder-credential-card__issuer">
      <Building2 size={17} aria-hidden="true" />
      <div>
        <span>Issued by</span>
        <strong>{credential.issuerName || credential.issuer || "Issuer not supplied"}</strong>
        {credential.issuerName && credential.issuer && <code title={credential.issuer}>{credential.issuer}</code>}
      </div>
    </div>

    <dl className="holder-credential-card__dates">
      <div><dt><CalendarDays size={14} aria-hidden="true" /> Issued</dt><dd>{displayDate(credential.issuedDate)}</dd></div>
      <div><dt><CalendarDays size={14} aria-hidden="true" /> Expires</dt><dd>{displayDate(credential.expiryDate)}</dd></div>
    </dl>

    <footer className="holder-credential-card__actions">
      {onPresent && (
        <button type="button" className="holder-primary-action" onClick={() => onPresent(credential)} aria-label={`Open a verifier request for ${credential.title}`}>
          <QrCode size={16} aria-hidden="true" /> Open request
        </button>
      )}
      {onViewDetails && (
        <button type="button" className="holder-secondary-action" onClick={() => onViewDetails(credential)} aria-label={`View details for ${credential.title}`}>
          <Eye size={16} aria-hidden="true" /> View details
        </button>
      )}
    </footer>
  </article>
);
