import React from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  IconBuildingBank, IconChecklist, IconClock, IconCpu, IconDatabase, IconFileText, IconHistory, IconHome, IconInbox,
  IconLogout, IconPalette, IconPlus, IconRotate, IconSearch, IconShieldLock, IconUsers, IconWallet,
} from "@tabler/icons-react";
import { BrandMark } from "../components/ssi/BrandMark.tsx";
import { LoadingState } from "../components/ui/States.tsx";
import { CommandPalette, type Command } from "../components/ui/CommandPalette.tsx";
import { roleLabel, useAuth } from "../context/AuthContext.ts";
import { NAVIGATION, type NavItem } from "../routes/navigation.ts";
import { areaForPath, useAppearance, useArtArea } from "../theme/appearance.ts";
import { ModeToggle } from "../theme/ModeToggle.tsx";

const ICON_PROPS = { size: 20, stroke: 1.75, "aria-hidden": true } as const;

const ICONS: Record<NavItem["icon"], React.ReactNode> = {
  wallet: <IconWallet {...ICON_PROPS} />,
  inbox: <IconInbox {...ICON_PROPS} />,
  shield: <IconShieldLock {...ICON_PROPS} />,
  users: <IconUsers {...ICON_PROPS} />,
  clock: <IconClock {...ICON_PROPS} />,
  home: <IconHome {...ICON_PROPS} />,
  file: <IconFileText {...ICON_PROPS} />,
  plus: <IconPlus {...ICON_PROPS} />,
  rotate: <IconRotate {...ICON_PROPS} />,
  search: <IconSearch {...ICON_PROPS} />,
  check: <IconChecklist {...ICON_PROPS} />,
  history: <IconHistory {...ICON_PROPS} />,
  database: <IconDatabase {...ICON_PROPS} />,
  cpu: <IconCpu {...ICON_PROPS} />,
  landmark: <IconBuildingBank {...ICON_PROPS} />,
};

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "?";
}

/** Tabler user dropdown (nav-item dropdown) controlled by React state instead of Bootstrap JS. */
/** `placement="up"` opens above the trigger (sidebar footer); default opens below. */
const UserMenu: React.FC<{ compact?: boolean; placement?: "down" | "up" }> = ({ compact = false, placement = "down" }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = React.useState(false);
  const [signingOut, setSigningOut] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);
  const buttonRef = React.useRef<HTMLButtonElement>(null);
  const menuId = React.useId();

  React.useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;
  const onSignOut = async () => {
    setSigningOut(true);
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div ref={rootRef} className={["nav-item", placement === "up" ? "dropup w-100" : "dropdown", open ? "show" : ""].filter(Boolean).join(" ")}>
      <button
        ref={buttonRef}
        type="button"
        className={["nav-link d-flex align-items-center lh-1 bg-transparent border-0", placement === "up" ? "w-100 px-3 py-2" : "p-0 px-2"].join(" ")}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="avatar avatar-sm bg-primary-lt" aria-hidden="true">{initials(user.displayName)}</span>
        <span className={compact ? "visually-hidden" : "d-block ps-2 text-start min-w-0"}>
          <span className="d-block text-truncate">{user.displayName}</span>
          <span className="d-block mt-1 small text-secondary">{roleLabel(user.role)}</span>
        </span>
        <span className="visually-hidden">Account menu</span>
      </button>
      <div
        id={menuId}
        className={[
          "dropdown-menu ssi-account-menu",
          placement === "up" ? "start-0 bottom-100 mb-2 w-100" : "dropdown-menu-end dropdown-menu-arrow end-0 top-100 mt-2",
          open ? "show" : "",
        ].filter(Boolean).join(" ")}
      >
        <div className="dropdown-item-text">
          <div className="fw-medium text-body">{user.displayName}</div>
          <div className="small text-secondary text-break">{roleLabel(user.role)} · {user.username}</div>
        </div>
        <div className="dropdown-divider" />
        <button type="button" className="dropdown-item" onClick={onSignOut} disabled={signingOut}>
          {signingOut ? <span className="spinner-border spinner-border-sm dropdown-item-icon" aria-hidden="true" /> : <IconLogout className="dropdown-item-icon" size={18} aria-hidden="true" />}
          Sign out
        </button>
      </div>
    </div>
  );
};

/** Tabler vertical layout (navbar-vertical + page-wrapper) for every authenticated role. */
export const AppShell: React.FC = () => {
  const { user } = useAuth();
  const { setPanelOpen, appearance } = useAppearance();
  const location = useLocation();
  const [open, setOpen] = React.useState(false);
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  const { logout } = useAuth();
  const navigate = useNavigate();
  useArtArea(areaForPath(location.pathname));

  React.useEffect(() => { setOpen(false); }, [location.pathname]);

  // Ctrl/Cmd + K opens the command palette anywhere in the workspace.
  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((value) => !value);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Tabler shows the vertical sidebar only when the document declares that layout.
  React.useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-bs-navbar-position", "vertical");
    return () => root.removeAttribute("data-bs-navbar-position");
  }, []);

  if (!user) return null;
  const items = NAVIGATION[user.role].filter((item) => !item.permission || user.permissions.includes(item.permission));
  const commands: Command[] = [
    ...items.map((item) => ({ id: `nav-${item.to}`, label: item.label, group: "Go to", icon: ICONS[item.icon], to: item.to })),
    { id: "appearance", label: "Change appearance", group: "Actions", icon: <IconPalette size={18} aria-hidden="true" />, run: () => setPanelOpen(true), keywords: "theme dark light colour background" },
    {
      id: "sign-out",
      label: "Sign out",
      group: "Actions",
      icon: <IconLogout size={18} aria-hidden="true" />,
      run: () => { void logout().then(() => navigate("/login", { replace: true })); },
      keywords: "logout exit",
    },
  ];

  return (
    <div className="page">
      <a className="visually-hidden-focusable position-absolute top-0 start-0 m-2 btn btn-primary z-3" href="#main">Skip to main content</a>
      <aside className="navbar navbar-vertical navbar-expand-lg" data-bs-theme={appearance.mode} aria-label="Workspace navigation">
        <div className="container-fluid">
          <button
            type="button"
            className={["navbar-toggler", open ? "" : "collapsed"].filter(Boolean).join(" ")}
            aria-controls="sidebar-menu"
            aria-expanded={open}
            aria-label="Toggle navigation"
            onClick={() => setOpen((value) => !value)}
          >
            <span className="navbar-toggler-icon" />
          </button>
          <div className="navbar-brand navbar-brand-autodark">
            <BrandMark inverse={appearance.mode === "dark"} to={items[0]?.to ?? "/"} />
          </div>
          <div className="navbar-nav flex-row align-items-center gap-1 d-lg-none">
            <ModeToggle className="btn-ghost-secondary" />
            <button type="button" className="btn btn-ghost-secondary btn-icon" aria-label="Search pages and actions" onClick={() => setPaletteOpen(true)}>
              <IconSearch size={20} aria-hidden="true" />
            </button>
            <button type="button" className="btn btn-ghost-secondary btn-icon" aria-label="Appearance" onClick={() => setPanelOpen(true)}>
              <IconPalette size={20} aria-hidden="true" />
            </button>
            <UserMenu compact />
          </div>
          <div className={["collapse navbar-collapse flex-column align-items-stretch", open ? "show" : ""].filter(Boolean).join(" ")} id="sidebar-menu">
            <nav className="w-100" aria-label={`${roleLabel(user.role)} workspace`}>
              <div className="ssi-sidebar-label text-uppercase small fw-medium px-3 pt-lg-4 pb-2">{roleLabel(user.role)} workspace</div>
              <ul className="navbar-nav">
                {items.map((item) => (
                  <li key={item.to} className="nav-item">
                    <NavLink to={item.to} end={item.end} className="nav-link">
                      <span className="nav-link-icon d-md-none d-lg-inline-block">{ICONS[item.icon]}</span>
                      <span className="nav-link-title">{item.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
            <div className="ssi-sidebar-user navbar-nav mt-auto pt-2 pb-lg-3 d-none d-lg-flex">
              <button type="button" className="nav-link bg-transparent border-0 w-100 px-3 py-2" onClick={() => setPanelOpen(true)}>
                <span className="nav-link-icon"><IconPalette size={20} stroke={1.75} aria-hidden="true" /></span>
                <span className="nav-link-title">Appearance</span>
              </button>
              <UserMenu placement="up" />
            </div>
          </div>
        </div>
      </aside>
      <div className="page-wrapper">
        <header className="ssi-commandbar d-none d-lg-block d-print-none" data-bs-theme={appearance.mode}>
          <div className="container-xl d-flex align-items-center gap-3">
            <button type="button" className="ssi-search-trigger" onClick={() => setPaletteOpen(true)} aria-label="Search pages and actions (Ctrl+K)">
              <IconSearch size={18} aria-hidden="true" />
              <span className="flex-fill text-start">Search or jump to…</span>
              <kbd className="ssi-kbd">Ctrl</kbd><kbd className="ssi-kbd">K</kbd>
            </button>
            <div className="ms-auto d-flex align-items-center gap-2">
              <span className="ssi-role-pill"><span className="ssi-pulse" aria-hidden="true" />{roleLabel(user.role)} workspace</span>
              <ModeToggle className="btn-ghost-secondary" />
              <button type="button" className="btn btn-ghost-secondary btn-icon" aria-label="Appearance" onClick={() => setPanelOpen(true)}>
                <IconPalette size={20} aria-hidden="true" />
              </button>
            </div>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="d-flex flex-column flex-fill">
          <React.Suspense fallback={<div className="page-body"><div className="container-xl"><div className="card"><LoadingState label="Loading page" /></div></div></div>}>
            <div key={location.pathname} className="ssi-page-enter d-flex flex-column flex-fill">
              <Outlet />
            </div>
          </React.Suspense>
        </main>
        <footer className="footer footer-transparent d-print-none">
          <div className="container-xl">
            <div className="row text-center align-items-center flex-row-reverse g-2">
              <div className="col-lg-auto ms-lg-auto small text-secondary">W3C VC 2.0 · OpenID4VCI · OpenID4VP · Data Integrity eddsa-jcs-2022</div>
              <div className="col-12 col-lg-auto small text-secondary">Secure SSI Platform</div>
            </div>
          </div>
        </footer>
      </div>
      <CommandPalette commands={commands} open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
};
