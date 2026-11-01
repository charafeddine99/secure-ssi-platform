import React from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { IconPalette } from "@tabler/icons-react";
import { BrandMark } from "../components/ssi/BrandMark.tsx";
import { LoadingState } from "../components/ui/States.tsx";
import { useAuth } from "../context/AuthContext.ts";
import { roleHomePath } from "../routes/navigation.ts";
import { useAppearance, useArtArea } from "../theme/appearance.ts";
import { ModeToggle } from "../theme/ModeToggle.tsx";

/** Tabler horizontal layout: top navbar, page-wrapper, transparent footer. */
export const PublicLayout: React.FC = () => {
  const { user } = useAuth();
  const { setPanelOpen, appearance } = useAppearance();
  const location = useLocation();
  useArtArea("public");
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => { setOpen(false); }, [location.pathname]);

  return (
    <div className="page">
      <a className="visually-hidden-focusable position-absolute top-0 start-0 m-2 btn btn-primary z-3" href="#main">Skip to main content</a>
      <header className="navbar navbar-expand-md ssi-topbar d-print-none" data-bs-theme={appearance.mode}>
        <div className="container-xl">
          <button
            type="button"
            className={["navbar-toggler", open ? "" : "collapsed"].filter(Boolean).join(" ")}
            aria-controls="public-menu"
            aria-expanded={open}
            aria-label="Toggle navigation"
            onClick={() => setOpen((value) => !value)}
          >
            <span className="navbar-toggler-icon" />
          </button>
          <div className="navbar-brand pe-0 pe-md-3">
            <BrandMark inverse={appearance.mode === "dark"} />
          </div>
          <div className="navbar-nav flex-row align-items-center gap-2 order-md-last">
            <ModeToggle className="btn-ghost-secondary" />
            <button type="button" className="btn btn-ghost-secondary btn-icon" aria-label="Appearance" onClick={() => setPanelOpen(true)}>
              <IconPalette size={20} aria-hidden="true" />
            </button>
            {user
              ? <NavLink to={roleHomePath(user.role)} className="btn btn-primary">Open workspace</NavLink>
              : <NavLink to="/login" className="btn btn-primary">Sign in</NavLink>}
          </div>
          <div className={["collapse navbar-collapse", open ? "show" : ""].filter(Boolean).join(" ")} id="public-menu">
            <nav aria-label="Public">
              <ul className="navbar-nav">
                <li className="nav-item"><NavLink to="/" end className="nav-link"><span className="nav-link-title">Overview</span></NavLink></li>
                <li className="nav-item"><NavLink to="/ecosystem" className="nav-link"><span className="nav-link-title">Trusted issuers</span></NavLink></li>
                <li className="nav-item"><NavLink to="/docs" className="nav-link"><span className="nav-link-title">How it works</span></NavLink></li>
              </ul>
            </nav>
          </div>
        </div>
      </header>
      <div className="page-wrapper">
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
              <div className="col-lg-auto ms-lg-auto small text-secondary">W3C VC 2.0 · OpenID4VCI / OpenID4VP · Data Integrity eddsa-jcs-2022</div>
              <div className="col-12 col-lg-auto small text-secondary">Secure SSI Platform</div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
};
