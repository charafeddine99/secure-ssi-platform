export type NavSection =
  | "dashboard"
  | "wallet"
  | "issuer"
  | "verifier"
  | "ai"
  | "recovery"
  | "blockchain";

interface SidebarProps {
  activeSection: NavSection;
  onSelectSection: (section: NavSection) => void;
}

interface NavItemConfig {
  id: NavSection;
  label: string;
  badge?: string;
  badgeType?: "green" | "blue" | "yellow";
  icon: JSX.Element;
}

export function Sidebar({ activeSection, onSelectSection }: SidebarProps) {
  const navItems: NavItemConfig[] = [
    {
      id: "dashboard",
      label: "Genel Bakış",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="7"/>
          <rect x="14" y="3" width="7" height="7"/>
          <rect x="14" y="14" width="7" height="7"/>
          <rect x="3" y="14" width="7" height="7"/>
        </svg>
      ),
    },
    {
      id: "wallet",
      label: "Kimlik Cüzdanım",
      badge: "W3C VC",
      badgeType: "blue",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4"/>
          <path d="M4 6v12c0 1.1.9 2 2 2h14v-4"/>
          <circle cx="18" cy="12" r="2"/>
        </svg>
      ),
    },
    {
      id: "issuer",
      label: "Belge Düzenleyici",
      badge: "Issuer",
      badgeType: "green",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          <line x1="9" y1="7" x2="15" y2="7"/>
          <line x1="9" y1="11" x2="15" y2="11"/>
        </svg>
      ),
    },
    {
      id: "verifier",
      label: "Doğrulayıcı Portal",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      ),
    },
    {
      id: "ai",
      label: "AI Güvenlik Merkezi",
      badge: "94.3%",
      badgeType: "green",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.5v1.5a2 2 0 0 1-2 2h0a2 2 0 0 1-2-2v-1.5C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z"/>
          <path d="M6 14v1a6 6 0 0 0 12 0v-1"/>
          <line x1="12" y1="19" x2="12" y2="22"/>
        </svg>
      ),
    },
    {
      id: "recovery",
      label: "Sosyal Kurtarma",
      badge: "3/5 Quorum",
      badgeType: "yellow",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      ),
    },
    {
      id: "blockchain",
      label: "Blockchain Gezgini",
      badge: "4 Sözleşme",
      badgeType: "blue",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
        </svg>
      ),
    },
  ];

  return (
    <aside className="web3-sidebar">
      <div className="sidebar-section-title">ANA MODÜLLER</div>
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              className={`sidebar-nav-item ${isActive ? "active" : ""}`}
              onClick={() => onSelectSection(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              {item.badge && (
                <span className={`nav-badge badge-${item.badgeType || "blue"}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="subu-badge">
          <div className="badge-logo-dot"></div>
          <div className="subu-text">
            <strong>SUBÜ Teknoloji</strong>
            <span>Bilgisayar Mühendisliği</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
