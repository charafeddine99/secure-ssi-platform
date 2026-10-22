import React from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

export const PublicLayout: React.FC = () => {
  const { pathname } = useLocation();

  return (
    <div className="public-layout">
      <div className="public-layout-content">
        <Outlet />
      </div>

      {pathname !== "/login" && (
        <footer className="app-public-footer">
          <span>© 2026 Secure SSI Platform</span>
          <nav aria-label="Footer navigation">
            <Link to="/ecosystem">Directory</Link>
            <Link to="/docs">Architecture</Link>
            <Link to="/login">Sign in</Link>
          </nav>
        </footer>
      )}
    </div>
  );
};
