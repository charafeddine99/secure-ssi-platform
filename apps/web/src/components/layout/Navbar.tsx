import { useState } from "react";
import { BrandMark } from "../common/BrandMark";

interface NavbarProps {
  isWalletConnected: boolean;
  onToggleWallet: () => void;
  walletAddress: string;
  userDid: string;
}

export function Navbar({
  isWalletConnected,
  onToggleWallet,
  walletAddress,
  userDid,
}: NavbarProps) {
  const [showDropdown, setShowDropdown] = useState(false);

  return (
    <header className="web3-navbar">
      <div className="navbar-left">
        <div className="platform-logo">
          <div className="logo-shield-icon"><BrandMark size={32} /></div>
          <div className="logo-text-group">
            <span className="logo-title">Secure SSI Platform</span>
          </div>
        </div>

        <div className="network-badge">
          <span className="pulsing-dot"></span>
          <span className="network-name">Local demo network</span>
        </div>
      </div>

      <div className="navbar-right">
        {isWalletConnected ? (
          <div className="wallet-connected-group">
            <div className="balance-pill">
              <span className="eth-icon">Ξ</span>
              <span className="balance-amount">Balance not loaded</span>
            </div>

            <div
              className="wallet-address-pill"
              onClick={() => setShowDropdown(!showDropdown)}
              title="Cüzdan ve DID Detayları"
            >
              <div className="avatar-dot"></div>
              <span className="address-text">{walletAddress.slice(0, 6)}...{walletAddress.slice(-4)}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 9l6 6 6-6"/>
              </svg>

              {showDropdown && (
                <div className="wallet-dropdown-menu">
                  <div className="dropdown-header">
                    <strong>Synthetic Demo Holder</strong>
                    <span className="role-tag">Demo profile · unassessed</span>
                  </div>
                  <div className="dropdown-item">
                    <span className="label">Aktif DID:</span>
                    <span className="value-code">{userDid.slice(0, 24)}...</span>
                  </div>
                  <div className="dropdown-item">
                    <span className="label">Ağ:</span>
                    <span className="value">Ethereum EVM (Local)</span>
                  </div>
                  <button className="dropdown-disconnect-btn" onClick={onToggleWallet}>
                    Cüzdan Bağlantısını Kes
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <button className="btn-connect-wallet" onClick={onToggleWallet}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="4" width="20" height="16" rx="2"/>
              <path d="M16 12h.01"/>
            </svg>
            Cüzdanı Bağla
          </button>
        )}
      </div>
    </header>
  );
}
