import { useState } from "react";

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
          <div className="logo-shield-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <path d="M9 12l2 2 4-4"/>
            </svg>
          </div>
          <div className="logo-text-group">
            <span className="logo-title">SECURE SSI</span>
            <span className="logo-subtitle">AI & Blockchain ID</span>
          </div>
        </div>

        <div className="network-badge">
          <span className="pulsing-dot"></span>
          <span className="network-name">Hardhat Localnet #1337</span>
        </div>
      </div>

      <div className="navbar-right">
        {isWalletConnected ? (
          <div className="wallet-connected-group">
            <div className="balance-pill">
              <span className="eth-icon">Ξ</span>
              <span className="balance-amount">2.450 ETH</span>
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
                    <strong>Charaf Eddine Bessanane</strong>
                    <span className="role-tag">Holder / Student</span>
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
