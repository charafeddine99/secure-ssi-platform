import React from "react";
import { IconCircleCheck, IconCircleX, IconHelpCircle } from "@tabler/icons-react";
import type { VerificationResult } from "../../api/presentation.ts";

type CheckState = "pass" | "fail" | "unknown";

interface Row { label: string; detail: string; state: CheckState }

function state(value: boolean | undefined): CheckState {
  if (value === true) return "pass";
  if (value === false) return "fail";
  return "unknown";
}

function riskState(level: string): CheckState {
  const upper = level.toUpperCase();
  if (upper === "LOW") return "pass";
  if (upper === "UNKNOWN" || upper === "") return "unknown";
  return "fail";
}

const STATE_BADGE: Record<CheckState, { className: string; text: string; icon: React.ReactNode }> = {
  pass: { className: "bg-green-lt", text: "Passed", icon: <IconCircleCheck size={20} className="text-green" aria-hidden="true" /> },
  fail: { className: "bg-red-lt", text: "Failed", icon: <IconCircleX size={20} className="text-red" aria-hidden="true" /> },
  unknown: { className: "bg-secondary-lt", text: "Not established", icon: <IconHelpCircle size={20} className="text-secondary" aria-hidden="true" /> },
};

/**
 * Shows each verification dimension separately. Cryptographic validity,
 * issuer trust, validity period, status, holder binding and the advisory risk
 * signal are distinct results; only the backend final policy decides.
 */
export const VerificationMatrix: React.FC<{ result: VerificationResult }> = ({ result }) => {
  const source = typeof result.details.ai_risk_source === "string" ? result.details.ai_risk_source as string : null;
  const rows: Row[] = [
    { label: "Credential structure & profile", detail: "Data model, context and type checks", state: state(result.credentialValid) },
    { label: "Signature / integrity", detail: "Data Integrity proof verified with the issuer key", state: state(result.signatureValid) },
    { label: "Issuer trust", detail: "Issuer found and active in the Trust Registry", state: state(result.issuerTrusted) },
    { label: "Holder binding", detail: "Presentation signed by the credential subject", state: state(result.holderBindingValid) },
    { label: "Validity period", detail: "validFrom / validUntil at verification time", state: state(result.expirationValid) },
    { label: "Revocation / suspension status", detail: "Bitstring status list checked", state: state(result.revocationStatusClear) },
    { label: "Request binding", detail: "Nonce, audience and session matched", state: state(result.challengeValid) },
    {
      label: "Advisory risk signal",
      detail: `Level ${result.aiRiskLevel}${source ? ` · source ${source}` : ""} · rule-based heuristic, not a fraud verdict`,
      state: riskState(result.aiRiskLevel),
    },
  ];
  return (
    <ul className="list-group list-group-flush ssi-checks" aria-label="Verification checks">
      {rows.map((row, index) => (
        <li key={row.label} className={`list-group-item ssi-check ssi-check-${row.state}`} style={{ "--i": index } as React.CSSProperties}>
          <div className="row align-items-center g-3">
            <div className="col-auto">{STATE_BADGE[row.state].icon}</div>
            <div className="col min-w-0">
              <div className="fw-medium">{row.label}</div>
              <div className="text-secondary small">{row.detail}</div>
            </div>
            <div className="col-auto"><span className={`badge ${STATE_BADGE[row.state].className}`}>{STATE_BADGE[row.state].text}</span></div>
          </div>
        </li>
      ))}
    </ul>
  );
};

/** Animated verdict seal: ring draws, then the mark appears. */
const ResultSeal: React.FC<{ accepted: boolean }> = ({ accepted }) => (
  <svg className={`ssi-seal ${accepted ? "ssi-seal-ok" : "ssi-seal-no"}`} viewBox="0 0 120 120" aria-hidden="true">
    <circle className="ssi-seal-track" cx="60" cy="60" r="50" />
    <circle className="ssi-seal-ring" cx="60" cy="60" r="50" pathLength={100} />
    {accepted
      ? <path className="ssi-seal-mark" d="M38 62 54 77 84 45" pathLength={100} />
      : <path className="ssi-seal-mark" d="M42 42 78 78M78 42 42 78" pathLength={100} />}
  </svg>
);

/**
 * Final policy outcome. Only an explicit ACCEPTED is shown as success; the
 * seal is decoration, the heading carries the result for assistive technology.
 */
export const PolicyBanner: React.FC<{ result: VerificationResult | null; pendingText?: string }> = ({ result, pendingText }) => {
  if (!result) {
    return (
      <div className="alert alert-secondary mb-0" role="status">
        <IconHelpCircle className="alert-icon" aria-hidden="true" />
        <div>
          <h4 className="alert-heading">No verification result yet</h4>
          <div className="alert-description">{pendingText ?? "The verifier has not received a presentation for this request."}</div>
        </div>
      </div>
    );
  }
  const accepted = result.finalPolicyResult === "ACCEPTED";
  return (
    <div className={`card ssi-verdict ${accepted ? "ssi-verdict-ok" : "ssi-verdict-no"}`} role="status">
      <div className="card-body d-flex flex-column flex-md-row align-items-center gap-4 text-center text-md-start">
        <ResultSeal accepted={accepted} />
        <div>
          <div className="ssi-verdict-kicker">Verifier policy decision</div>
          <h2 className="ssi-verdict-title">{accepted ? "Accepted" : "Rejected"}</h2>
          <p className="mb-0 text-secondary">
            {accepted
              ? "All mandatory checks passed under this policy."
              : "A mandatory check failed or could not be established."}
          </p>
        </div>
      </div>
    </div>
  );
};
