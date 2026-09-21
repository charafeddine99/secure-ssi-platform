import React, { useState } from "react";
import { useWallet } from "../../context/WalletContext";

export interface VerifiableCredential {
  id: string;
  type: string;
  issuer: string;
  issuanceDate: string;
  expirationDate: string;
  status: "VALID" | "REVOKED" | "SUSPENDED";
  trustStatus: "Blockchain Anchored" | "W3C Verified" | "AI Cleared";
  claims: Record<string, string>;
  proofValue: string;
}

const INITIAL_CREDENTIALS: VerifiableCredential[] = [
  {
    id: "urn:uuid:subu-diploma-2026-b210109591",
    type: "UniversityDegreeCredential",
    issuer: "did:web:subu.edu.tr",
    issuanceDate: "2026-06-25",
    expirationDate: "2036-06-25",
    status: "VALID",
    trustStatus: "Blockchain Anchored",
    claims: {
      "Full Name": "Charaf Eddine Bessanane",
      "Student ID": "B210109591",
      "Department": "Computer Engineering",
      "Degree": "Bachelor of Science",
      "GPA": "3.82 / 4.00"
    },
    proofValue: "z3h8B1a94f21SUBUSignedProofValueValidW3C2026Ed25519"
  },
  {
    id: "urn:uuid:kyc-tier1-did-88912",
    type: "IdentityVerificationCredential",
    issuer: "did:ssi:platform:governance-authority",
    issuanceDate: "2026-09-20",
    expirationDate: "2027-09-20",
    status: "VALID",
    trustStatus: "AI Cleared",
    claims: {
      "Verification Level": "Tier 1 Biometric & Device",
      "AI Fraud Risk Score": "8 / 100",
      "Security Evaluation": "PASSED (Low Risk)"
    },
    proofValue: "z8A4c91Bde77LinkedDataProofEd25519Signature"
  }
];

export const CredentialVault: React.FC = () => {
  const { account } = useWallet();
  const [credentials, setCredentials] = useState<VerifiableCredential[]>(INITIAL_CREDENTIALS);
  const [selectedVC, setSelectedVC] = useState<VerifiableCredential | null>(null);
  const [isIssuing, setIsIssuing] = useState<boolean>(false);
  const [issuanceError, setIssuanceError] = useState<string | null>(null);

  const handleRequestNewCredential = async () => {
    if (!account) {
      setIssuanceError("Please connect your wallet first.");
      return;
    }

    setIsIssuing(true);
    setIssuanceError(null);

    try {
      // Call Layer 3 API (http://127.0.0.1:8001/api/issue_credential)
      const res = await fetch("http://127.0.0.1:8001/api/issue_credential", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wallet_address: account,
          did_id: `did:key:z6Mku${account.slice(2, 10)}UserWallet`,
          ip_address: "192.168.1.100",
          device_fingerprint: "fp_web_dashboard_client_v1",
          recent_failed_attempts: 0
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned status ${res.status}`);
      }

      const data = await res.json();
      const rawVC = data.verifiable_credential;

      const newCred: VerifiableCredential = {
        id: rawVC.id,
        type: rawVC.type[1] || "IdentityVerificationCredential",
        issuer: rawVC.issuer,
        issuanceDate: rawVC.issuanceDate.split("T")[0],
        expirationDate: rawVC.expirationDate.split("T")[0],
        status: "VALID",
        trustStatus: "AI Cleared",
        claims: {
          "Subject DID": rawVC.credentialSubject.id,
          "Wallet": rawVC.credentialSubject.walletAddress,
          "KYC Status": rawVC.credentialSubject.kycLevel,
          "AI Risk Score": `${data.risk_score} / 100`
        },
        proofValue: rawVC.proof.proofValue
      };

      setCredentials((prev) => [newCred, ...prev]);
    } catch (err: any) {
      console.error("Issuance failed:", err);
      setIssuanceError(err.message || "Failed to request credential from SSI Layer 3 API.");
    } finally {
      setIsIssuing(false);
    }
  };

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
            W3C JSON-LD Verifiable Credentials stored in your self-sovereign identity wallet.
          </p>
        </div>

        <button
          onClick={handleRequestNewCredential}
          disabled={isIssuing}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white font-medium text-sm rounded-xl transition duration-150 shadow-lg shadow-indigo-600/20"
        >
          {isIssuing ? (
            <>
              <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Verifying with AI...</span>
            </>
          ) : (
            <>
              <span>+</span>
              <span>Issue New VC</span>
            </>
          )}
        </button>
      </div>

      {issuanceError && (
        <div className="mt-4 p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400 flex items-center justify-between">
          <span>{issuanceError}</span>
          <button onClick={() => setIssuanceError(null)} className="text-rose-400 hover:text-white font-bold ml-2">
            ✕
          </button>
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
                <span className="text-slate-400 font-semibold block mb-1">Ed25519 Linked Data Proof:</span>
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
