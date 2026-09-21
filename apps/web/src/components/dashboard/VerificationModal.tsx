import React, { useState } from "react";
import { useWallet } from "../../context/WalletContext";

interface VerificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onVerificationResult?: (success: boolean) => void;
}

export const VerificationModal: React.FC<VerificationModalProps> = ({
  isOpen,
  onClose,
  onVerificationResult
}) => {
  const { account } = useWallet();
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [decisionFeedback, setDecisionFeedback] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleApprove = async () => {
    setIsProcessing(true);
    setDecisionFeedback(null);

    // Simulate cryptographic selective disclosure presentation & zero-knowledge verification
    setTimeout(() => {
      setIsProcessing(false);
      setDecisionFeedback("APPROVED: Verifiable Presentation signed and securely delivered to dApp.");
      if (onVerificationResult) onVerificationResult(true);
      setTimeout(() => {
        onClose();
        setDecisionFeedback(null);
      }, 1500);
    }, 1200);
  };

  const handleReject = () => {
    setDecisionFeedback("REJECTED: Verification request was declined by the identity owner.");
    if (onVerificationResult) onVerificationResult(false);
    setTimeout(() => {
      onClose();
      setDecisionFeedback(null);
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative overflow-hidden">
        {/* Glow accent */}
        <div className="absolute -top-12 -right-12 w-32 h-32 bg-indigo-500/20 rounded-full blur-2xl pointer-events-none"></div>

        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-lg shadow-lg shadow-indigo-500/20">
              🛡️
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Identity Verification Request</h3>
              <p className="text-xs text-slate-400">Origin: <span className="text-indigo-400 font-mono">app.defi-lending.eth</span></p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-sm font-semibold p-1"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="py-5 space-y-4">
          <p className="text-xs text-slate-300 leading-relaxed">
            A third-party dApp is requesting proof of your identity credentials. Please review the claims before approving the presentation:
          </p>

          {/* Requested Claims Card */}
          <div className="bg-slate-950/80 rounded-2xl p-4 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
              <span>Requested Claims</span>
              <span className="text-emerald-400 text-[11px] bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                W3C Verified
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-slate-800/40">
                <span className="text-slate-400">Target DID:</span>
                <span className="font-mono text-slate-200 text-[11px] truncate max-w-[190px]">
                  {account ? `did:key:z6Mku${account.slice(2, 10)}...` : "did:key:z6MkuBesnaSubu"}
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-slate-800/40">
                <span className="text-slate-400">Degree Claim:</span>
                <span className="text-slate-200 font-medium">B.Sc. Computer Engineering</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-slate-800/40">
                <span className="text-slate-400">KYC Status:</span>
                <span className="text-emerald-400 font-medium">Tier 1 Authenticated</span>
              </div>
            </div>
          </div>

          {/* Feedback notice */}
          {decisionFeedback && (
            <div
              className={`p-3 rounded-xl text-xs font-medium ${
                decisionFeedback.startsWith("APPROVED")
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
              }`}
            >
              {decisionFeedback}
            </div>
          )}
        </div>

        {/* Modal Actions */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <button
            onClick={handleReject}
            disabled={isProcessing}
            className="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white font-medium text-xs rounded-xl transition duration-150 border border-slate-700/50"
          >
            Reject Request
          </button>
          <button
            onClick={handleApprove}
            disabled={isProcessing}
            className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white font-medium text-xs rounded-xl transition duration-150 shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-1.5"
          >
            {isProcessing ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Signing Proof...</span>
              </>
            ) : (
              "Approve & Sign"
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
