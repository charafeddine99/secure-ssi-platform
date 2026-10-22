import React from "react";
import { CheckCircle2, CircleHelp, Info, XCircle } from "lucide-react";
import { NinePointVerificationResult } from "../../services/api";

interface NinePointVerificationMatrixProps {
  result: NinePointVerificationResult;
  disclosedClaims?: Record<string, unknown>;
  aiRiskScore?: number;
  sessionId?: string;
}

export const NinePointVerificationMatrix: React.FC<NinePointVerificationMatrixProps> = ({
  result,
  disclosedClaims,
  aiRiskScore,
  sessionId,
}) => {
  const accepted = result.finalPolicyResult === "ACCEPTED";
  const items = [
    { id: "credential", label: "Credential profile", value: result.credentialValid, detail: result.evaluations?.credential },
    { id: "issuer", label: "Issuer trust", value: result.issuerTrusted, detail: result.evaluations?.issuer },
    { id: "signature", label: "Signature", value: result.signatureValid, detail: result.evaluations?.signature },
    { id: "holder", label: "Holder binding", value: result.holderBindingValid, detail: result.evaluations?.holder_binding },
    { id: "expiry", label: "Validity period", value: result.expirationValid, detail: result.evaluations?.expiration },
    { id: "status", label: "Credential status", value: result.revocationStatusClear, detail: result.evaluations?.revocation },
    { id: "challenge", label: "Challenge", value: result.challengeValid, detail: result.evaluations?.challenge },
  ];

  return (
    <section className="verifier-policy-result" aria-labelledby="policy-result-title">
      <header className="verifier-policy-result__header">
        <div><p className="workspace-eyebrow">Identity Service response</p><h3 id="policy-result-title">Policy evaluation</h3><p>Individual values below are included in the returned session response.</p></div>
        <span className={"verifier-policy-decision " + (accepted ? "is-accepted" : "is-rejected")}>{accepted ? <CheckCircle2 size={16} aria-hidden="true" /> : <XCircle size={16} aria-hidden="true" />}{result.finalPolicyResult}</span>
      </header>

      {sessionId && <p className="verifier-policy-session">Session reference <code>{sessionId}</code></p>}

      <ul className="verifier-policy-checks">
        {items.map((item) => (
          <li className={item.value ? "is-valid" : "is-invalid"} key={item.id}>
            {item.value ? <CheckCircle2 size={17} aria-hidden="true" /> : <XCircle size={17} aria-hidden="true" />}
            <span><strong>{item.label}</strong>{item.detail && <small>{item.detail}</small>}</span>
            <b>{item.value ? "Passed" : "Not passed"}</b>
          </li>
        ))}
        <li className="is-advisory">
          <Info size={17} aria-hidden="true" />
          <span><strong>Risk signal</strong><small>Advisory value returned by the service</small></span>
          <b>{result.aiRiskLevel}{aiRiskScore !== undefined ? " · " + aiRiskScore + "/100" : ""}</b>
        </li>
        <li className={result.blockchainAnchored ? "is-valid" : "is-unknown"}>
          {result.blockchainAnchored ? <CheckCircle2 size={17} aria-hidden="true" /> : <CircleHelp size={17} aria-hidden="true" />}
          <span><strong>Blockchain anchor</strong><small>Optional integrity record; separate from credential validity</small></span>
          <b>{result.blockchainAnchored ? "Reported" : "Not reported"}</b>
        </li>
      </ul>

      {disclosedClaims && Object.keys(disclosedClaims).length > 0 && (
        <div className="verifier-returned-claims">
          <div><h4>Claims returned by the service</h4><p>These values are shown as returned. The current Data Integrity profile does not provide cryptographic selective disclosure.</p></div>
          <dl>{Object.entries(disclosedClaims).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
        </div>
      )}
    </section>
  );
};
