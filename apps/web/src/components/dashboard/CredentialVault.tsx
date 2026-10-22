import React, { useState } from "react";

export interface VerifiableCredential {
  id: string;
  type: string;
  issuer: string;
  issuanceDate: string;
  expirationDate: string;
  status: "UNKNOWN" | "VALID" | "REVOKED" | "SUSPENDED";
  trustStatus: "Synthetic demo fixture";
  claims: Record<string, string>;
  proofValue: string;
}

const INITIAL_CREDENTIALS: VerifiableCredential[] = [
  {
    id: "urn:uuid:synthetic-degree-demo-0001",
    type: "UniversityDegreeCredential",
    issuer: "did:example:issuer-001",
    issuanceDate: "2026-06-25",
    expirationDate: "2036-06-25",
    status: "UNKNOWN",
    trustStatus: "Synthetic demo fixture",
    claims: {
      "Example name": "Synthetic Demo Holder",
      "Example identifier": "DEMO-0001",
      "Example department": "Example Department",
      "Example degree": "Synthetic degree fixture",
      "Example GPA": "Not assessed"
    },
    proofValue: "DEMO_ONLY_NO_CREDENTIAL_PROOF"
  },
  {
    id: "urn:uuid:synthetic-identity-demo-0002",
    type: "IdentityVerificationCredential",
    issuer: "did:example:issuer-002",
    issuanceDate: "2026-09-20",
    expirationDate: "2027-09-20",
    status: "UNKNOWN",
    trustStatus: "Synthetic demo fixture",
    claims: {
      "Example note": "Synthetic demo only; no biometric or fraud evaluation was performed."
    },
    proofValue: "DEMO_ONLY_NO_CREDENTIAL_PROOF"
  }
];

export const CredentialVault: React.FC = () => {
  const [credentials] = useState<VerifiableCredential[]>(INITIAL_CREDENTIALS);
  const [selectedVC, setSelectedVC] = useState<VerifiableCredential | null>(null);
  const issuanceError = "This legacy vault is a static fixture. Its retired issuance endpoint is disabled; use the current issuer flow.";

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg text-lg">🪪</span>
            <h2 className="text-xl font-bold text-white tracking-tight">Credential Vault</h2>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Synthetic credential fixtures only. This component is not connected to an issuer or wallet.
          </p>
        </div>

        <button
          disabled
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white font-medium text-sm rounded-xl transition duration-150 shadow-lg shadow-indigo-600/20"
        >
          <span>Issuance unavailable</span>
        </button>
      </div>

      {issuanceError && (
        <div className="mt-4 p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400 flex items-center justify-between">
          <span>{issuanceError}</span>
        </div>
      )}

      {/* Credentials Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-6">
        {credentials.map((cred) => (
          <div
            key={cred.id}
            className="group relative bg-slate-950/60 border border-slate-800/80 hover:border-indigo-500/50 rounded-xl p-5 transition-all duration-200 hover:shadow-xl hover:shadow-indigo-500/5 flex flex-col justify-between"
          >
            <div>
              {/* Top Row: Type & Trust Status Badge */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <span className="font-semibold text-white text-base tracking-tight group-hover:text-indigo-400 transition-colors">
                  {cred.type}
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  {cred.trustStatus}
                </span>
              </div>

              {/* Issuer & Date Meta */}
              <div className="space-y-1.5 text-xs text-slate-400 mb-4">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Issuer:</span>
                  <span className="font-mono text-slate-300 truncate max-w-[200px]" title={cred.issuer}>
                    {cred.issuer}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Issuance Date:</span>
                  <span className="text-slate-300">{cred.issuanceDate}</span>
                </div>
              </div>

              {/* Claims Preview */}
              <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/50 space-y-1.5 text-xs">
                {Object.entries(cred.claims).slice(0, 3).map(([key, val]) => (
                  <div key={key} className="flex justify-between items-center">
                    <span className="text-slate-400">{key}:</span>
                    <span className="text-slate-200 font-medium truncate max-w-[170px]">{val}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Bottom Actions */}
            <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs">
              <span className="font-mono text-[11px] text-slate-500 truncate max-w-[180px]">
                {cred.id}
              </span>
              <button
                onClick={() => setSelectedVC(cred)}
                className="text-indigo-400 hover:text-indigo-300 font-medium hover:underline transition"
              >
                Inspect Proof →
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Inspect VC Modal */}
      {selectedVC && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedVC.type}</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{selectedVC.id}</p>
              </div>
              <button
                onClick={() => setSelectedVC(null)}
                className="text-slate-400 hover:text-white text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-400 font-semibold block mb-2">Subject Claims:</span>
                {Object.entries(selectedVC.claims).map(([k, v]) => (
                  <div key={k} className="flex justify-between py-1 border-b border-slate-900 last:border-0">
                    <span className="text-slate-400">{k}:</span>
                    <span className="text-slate-200 font-medium">{v}</span>
                  </div>
                ))}
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-400 font-semibold block mb-1">Proof placeholder (not verified):</span>
                <p className="font-mono text-[11px] text-indigo-400 break-all bg-indigo-950/30 p-2 rounded border border-indigo-900/30">
                  {selectedVC.proofValue}
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedVC(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
